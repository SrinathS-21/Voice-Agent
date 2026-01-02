"""
Google Speech adapter (scaffold)

This file provides a minimal adapter that implements the same
behaviour the codebase expects from a websocket-like connection:
- supports `async with GoogleSpeechService.connect() as conn:`
- `await conn.send(...)` sends config (str) or audio (bytes)
- `async for msg in conn:` yields incoming provider messages (str or bytes)

The current implementation is a scaffold to get the integration wired
into the codebase; real Google Speech + Gemini streaming will be added
under this module in a follow-up step.
"""

import asyncio
import json
import threading
import inspect
from contextlib import asynccontextmanager
from typing import Any, Optional
import time

from app.core.logging import get_logger

logger = get_logger(__name__)


try:
    from google.cloud import speech_v1 as speech
    from google.cloud.speech_v1 import types as speech_types
except Exception:
    speech = None

# Always import the Gemini client helper; it's used to generate assistant
# responses from transcripts regardless of whether Google Speech is
# available.
from websocket_server.services.gemini_client import get_gemini_client


class _Adapter:
    def __init__(self, loop: asyncio.AbstractEventLoop, agent_metadata: Optional[dict] = None):
        self._loop = loop
        self.agent_metadata = agent_metadata or {}
        self._in_queue: asyncio.Queue = asyncio.Queue()
        self._out_queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
        self._thread: Optional[threading.Thread] = None
        self._recognition_config = None
        # recent prompts map for deduplication: normalized_prompt -> last_timestamp
        self._recent_prompts = {}

    async def send(self, data: Any):
        """Accept config (str) or audio chunk (bytes).

        - If `data` is a str, treat it as the config JSON and configure
          recognition parameters.
        - If bytes, forward to the background thread via the input queue.
        """
        if isinstance(data, str):
            try:
                cfg = json.loads(data)
                # Extract listen provider audio settings if present
                audio = cfg.get("audio", {})
                input_cfg = audio.get("input", {})
                encoding = input_cfg.get("encoding", "mulaw")
                sample_rate = int(input_cfg.get("sample_rate", 8000))
                # Map encoding to Google enum
                if encoding.lower() in ("mulaw", "ulaw"):
                    enc = speech.RecognitionConfig.AudioEncoding.MULAW if speech else None
                elif encoding.lower() == "linear16":
                    enc = speech.RecognitionConfig.AudioEncoding.LINEAR16 if speech else None
                else:
                    enc = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED if speech else None

                if speech:
                    self._recognition_config = speech.RecognitionConfig(
                        encoding=enc,
                        sample_rate_hertz=sample_rate,
                        language_code=cfg.get("agent", {}).get("language", "en-US"),
                    )
                logger.info("[GoogleSpeechService] Config applied (scaffold)")
                # Start background thread when config applied
                if not self._thread:
                    self._thread = threading.Thread(target=self._responses_thread, daemon=True)
                    self._thread.start()
                # Notify consumers that settings were applied (Deepgram event compatibility)
                settings_msg = {"type": "SettingsApplied"}
                self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(settings_msg))
            except Exception as e:
                logger.error("Failed to parse provider config", error=str(e))
        else:
            # audio bytes
            await self._in_queue.put(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._closed:
            raise StopAsyncIteration
        logger.info("Adapter __anext__ waiting for message")
        msg = await self._out_queue.get()
        logger.info(f"Adapter __anext__ got message: {str(msg)[:200]}...")
        return msg

    async def close(self):
        # Signal background thread to stop
        await self._in_queue.put(None)
        self._closed = True
        if self._thread:
            self._thread.join(timeout=1.0)

    def _call_gemini_and_enqueue(self, prompt_text: str, ag_conf: dict):
        """Call Gemini safely with a small dedupe window and enqueue assistant and function responses."""
        now = time.time()
        key = ' '.join(prompt_text.split())  # normalize whitespace
        last = self._recent_prompts.get(key)
        if last and (now - last) < 3.0:
            try:
                logger.info("Skipping duplicate Gemini prompt", prompt_preview=key[:200])
            except Exception:
                pass
            return
        self._recent_prompts[key] = now

        try:
            gemini = get_gemini_client()
            functions = ag_conf.get('functions') if isinstance(ag_conf, dict) else None

            # Determine max output tokens for this call: prefer agent config override, then settings default
            from app.core.config import settings
            max_tokens = None
            try:
                if isinstance(ag_conf, dict):
                    # Support common override locations
                    max_tokens = ag_conf.get('max_output_tokens') or (ag_conf.get('think') and ag_conf.get('think').get('max_output_tokens'))
                if not max_tokens:
                    max_tokens = getattr(settings, 'GEMINI_MAX_OUTPUT_TOKENS', 512)
            except Exception:
                max_tokens = 512

            logger.info("Calling Gemini with max_output_tokens", max_output_tokens=max_tokens)

            coro = gemini.generate_text(prompt_text, temperature=0.3, max_tokens=int(max_tokens), functions=functions) if functions else gemini.generate_text(prompt_text, temperature=0.3, max_tokens=int(max_tokens))
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            gem_resp = fut.result(timeout=30)

            try:
                logger.info("Gemini raw response", response=gem_resp)
            except Exception:
                pass

            assistant_text = _extract_text_from_gemini_response(gem_resp)
            try:
                logger.info("Gemini assistant text extracted", assistant_text=assistant_text)
            except Exception:
                pass

            if assistant_text:
                assistant_msg = {
                    "type": "ConversationText",
                    "role": "assistant",
                    "content": assistant_text,
                    "is_final": True
                }
                try:
                    logger.info("Enqueuing assistant message to adapter out_queue", content=assistant_text)
                except Exception:
                    pass
                self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(assistant_msg))

            func_call = _extract_function_call_from_gemini_response(gem_resp)
            if func_call:
                import uuid, json as _json
                func_id = str(uuid.uuid4())
                functions_block = [
                    {
                        "name": func_call.get('name'),
                        "id": func_id,
                        "arguments": _json.dumps(func_call.get('arguments', {}))
                    }
                ]
                func_msg = {
                    "type": "FunctionCallRequest",
                    "functions": functions_block
                }
                self._loop.call_soon_threadsafe(self._out_queue.put_nowait, _json.dumps(func_msg))

        except Exception as e:
            logger.error("Error calling Gemini for assistant response", error=str(e))
            err_msg = {"type": "Error", "message": str(e)}
            self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(err_msg))
    def _responses_thread(self):
        """Background thread: consumes audio from asyncio queue and
        calls Google's streaming_recognize; pushes transcripts into
        the adapter out queue via the event loop.
        """
        if not speech:
            logger.warning("google-cloud-speech not available; running scaffold thread")
            return

        client = speech.SpeechClient()

        def request_generator(send_config: bool = True):
            # First message: streaming config (only if caller expects it)
            if send_config and self._recognition_config:
                streaming_config = speech.StreamingRecognitionConfig(
                    config=self._recognition_config,
                    interim_results=True,
                )
                yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)

            while True:
                # Blocking get from asyncio queue
                fut = asyncio.run_coroutine_threadsafe(self._in_queue.get(), self._loop)
                chunk = fut.result()
                if chunk is None:
                    break
                # Ensure we pass raw bytes to the protobuf request (some callers
                # provide `bytearray` or `memoryview` objects)
                if isinstance(chunk, (bytearray, memoryview)):
                    chunk = bytes(chunk)
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        try:
            # Attempt the most common call form first (requests-only)
            # Default: have the generator emit the initial streaming_config
            responses = client.streaming_recognize(requests=request_generator(True))
            for response in responses:
                for result in response.results:
                    transcripts = [alt.transcript for alt in result.alternatives]
                    best = transcripts[0] if transcripts else ""
                    msg = {
                        "type": "ConversationText",
                        "role": "user",
                        "content": best,
                        "is_final": result.is_final
                    }
                    # Push JSON string to out queue
                    self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(msg))

                    # Also call Gemini for NLU/assistant response using the transcript
                    # Only call Gemini for non-empty, final transcripts
                    if best and result.is_final:
                        try:
                            # Build prompt: include agent system_prompt if available
                            agent_cfg = getattr(self, 'agent_metadata', {}) or {}
                            ag_conf = agent_cfg.get('agent_config') or {}
                            system_prompt = ag_conf.get('system_prompt') if isinstance(ag_conf, dict) else None
                            if system_prompt:
                                prompt_text = system_prompt + "\nUser said: " + best
                            else:
                                prompt_text = best
                            try:
                                logger.info("Sending prompt to Gemini", prompt=prompt_text)
                            except Exception:
                                pass

                            # Use helper to call Gemini with deduplication and enqueue responses
                            self._call_gemini_and_enqueue(prompt_text, ag_conf)

                        except Exception as e:
                            logger.error("Error calling Gemini for assistant response", error=str(e))
                            err_msg = {"type": "Error", "message": str(e)}
                            self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(err_msg))
        except TypeError as e:
            # Some google-cloud-speech versions expose a helper whose signature
            # expects the streaming config as the first positional argument
            # (or under a different parameter name). Try a few common variants
            # to be robust across installed library versions.
            try:
                # Build streaming_config outside generator for reuse
                streaming_config = None
                if self._recognition_config:
                    streaming_config = speech.StreamingRecognitionConfig(
                        config=self._recognition_config,
                        interim_results=True,
                    )

                # Inspect signature and attempt calling accordingly
                sig = inspect.signature(client.streaming_recognize)
                params = list(sig.parameters.keys())

                # Try named parameter 'streaming_config' or 'config'
                # When we pass the streaming_config as an explicit parameter,
                # the request generator must NOT emit the initial config again.
                if 'streaming_config' in params:
                    responses = client.streaming_recognize(streaming_config=streaming_config, requests=request_generator(False))
                elif 'config' in params:
                    responses = client.streaming_recognize(config=streaming_config, requests=request_generator(False))
                else:
                    # Fallback: positional first-arg style
                    responses = client.streaming_recognize(streaming_config, request_generator(False))

                for response in responses:
                    for result in response.results:
                        transcripts = [alt.transcript for alt in result.alternatives]
                        best = transcripts[0] if transcripts else ""
                        msg = {
                            "type": "ConversationText",
                            "role": "user",
                            "content": best,
                            "is_final": result.is_final
                        }
                        # Push JSON string to out queue
                        self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(msg))

                        # Only call Gemini for non-empty, final transcripts
                        if best and result.is_final:
                            try:
                                # Build prompt: include agent system_prompt if available
                                agent_cfg = getattr(self, 'agent_metadata', {}) or {}
                                ag_conf = agent_cfg.get('agent_config') or {}
                                system_prompt = ag_conf.get('system_prompt') if isinstance(ag_conf, dict) else None
                                if system_prompt:
                                    prompt_text = system_prompt + "\nUser said: " + best
                                else:
                                    prompt_text = best
                                try:
                                    logger.info("Sending prompt to Gemini", prompt=prompt_text)
                                except Exception:
                                    pass

                                # Use helper to call Gemini with deduplication and enqueue responses
                                self._call_gemini_and_enqueue(prompt_text, ag_conf)

                            except Exception as e:
                                logger.error("Error calling Gemini for assistant response", error=str(e))
                                err_msg = {"type": "Error", "message": str(e)}
                                self._loop.call_soon_threadsafe(self._out_queue.put_nowait, json.dumps(err_msg))

            except Exception as e2:
                logger.error("Error in Google streaming thread", error=str(e2))
        except Exception as e:
            logger.error("Error in Google streaming thread", error=str(e))


def _extract_text_from_gemini_response(resp: dict) -> str:
    """Try common Gemini response shapes to extract reply text."""
    if not resp:
        return ""
    # Common shapes: {'outputs':[{'content':[{'type':'output_text','text':'...'}]}]}
    try:
        outputs = resp.get("outputs") or resp.get("candidates")
        if isinstance(outputs, list) and outputs:
            # Iterate outputs/candidates and try to extract text from common fields
            for out in outputs:
                # Case A: out is dict with 'content' as a dict containing 'parts'
                if isinstance(out, dict):
                    content = out.get("content")
                    if isinstance(content, dict):
                        parts = content.get("parts") or content.get("content")
                        if isinstance(parts, list) and parts:
                            texts = []
                            for p in parts:
                                if isinstance(p, dict):
                                    t = p.get("text") or p.get("payload") or p.get("data")
                                    if isinstance(t, str) and t.strip():
                                        texts.append(t.strip())
                            if texts:
                                return "\n".join(texts)
                        # Sometimes content may directly include a 'text' field
                        if isinstance(content.get("text"), str) and content.get("text").strip():
                            return content.get("text").strip()

                    # Case B: out itself may have a 'text' field
                    if isinstance(out.get("text"), str) and out.get("text").strip():
                        return out.get("text").strip()

        # Flat 'text' or 'response' fields at root
        if isinstance(resp.get("text"), str) and resp.get("text").strip():
            return resp.get("text").strip()
        if isinstance(resp.get("response"), str) and resp.get("response").strip():
            return resp.get("response").strip()
    except Exception:
        logger.debug("Failed to parse Gemini response for text", raw=resp)
        return ""
    # Nothing found
    logger.debug("No assistant text found in Gemini response", raw=resp)
    return ""


def _extract_function_call_from_gemini_response(resp: dict) -> dict:
    """Detect function/tool-call information in Gemini response.

    Returns dict: {name: str, arguments: dict} or None
    """
    if not resp:
        return None
    # Look for common keys
    try:
        # Some Gemini responses may include a 'tool_call' or 'function_call' block
        for key in ("tool_call", "function_call", "toolcall"):
            if key in resp and isinstance(resp[key], dict):
                data = resp[key]
                name = data.get("name") or data.get("tool")
                args = data.get("arguments") or data.get("args") or {}
                return {"name": name, "arguments": args}

        # Sometimes tool call info may be in outputs' metadata
        outputs = resp.get("outputs") or resp.get("candidates")
        if isinstance(outputs, list):
            for out in outputs:
                meta = out.get("metadata") or out.get("tool_call")
                if isinstance(meta, dict) and (meta.get("name") or meta.get("tool")):
                    return {"name": meta.get("name") or meta.get("tool"), "arguments": meta.get("arguments") or {}}
    except Exception:
        return None
    return None


class GoogleSpeechService:
    @staticmethod
    @asynccontextmanager
    async def connect(agent_metadata: dict | None = None):
        """Connect to Google Speech (scaffold).

        `agent_metadata` is accepted for parity with other providers; adapters may
        use it to select TTS voices or NLU routing.
        """
        loop = asyncio.get_event_loop()
        adapter = _Adapter(loop, agent_metadata=agent_metadata)
        try:
            logger.info("[GoogleSpeechService] connect()", agent_metadata=agent_metadata)
            yield adapter
        finally:
            await adapter.close()
