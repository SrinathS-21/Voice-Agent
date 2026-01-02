"""
Audio Stream Handler
Handles audio streaming between Twilio and Deepgram
"""

import asyncio
import base64
import json
import time
from typing import Optional

from app.core.logging import get_logger
from app.utils.websocket_helper import WebSocketHelper
from websocket_server.services.db_logger import DatabaseLogger

logger = get_logger(__name__)
db_logger = DatabaseLogger()


class AudioStreamHandler:
    """Handles bidirectional audio streaming"""
    
    BUFFER_SIZE = 160  # 20ms of mulaw audio at 8kHz (160 samples @ 8kHz, 1 byte/sample)
    
    # Track greeting latency (call answer -> first agent audio)
    _call_start_times = {}
    # Track think latency (user utterance end -> assistant generation)
    _last_user_utterance_end_times = {}
    # Track when config was sent to Deepgram to measure apply latency
    _config_sent_times = {}
    
    # 🆕 Detailed latency tracking for STT, LLM, TTS
    _stt_start_times = {}  # When user started speaking
    _llm_start_times = {}  # When transcript sent to LLM
    _tts_start_times = {}  # When TTS generation started
    
    # Auto-hangup after farewell
    _farewell_detected = {}  # Track if farewell was said
    _last_activity_time = {}  # Track last user activity

    # TTS management: avoid overlapping speak tasks per stream
    _tts_tasks: dict = {}
    # Queues for pending TTS per stream (play sequentially after current finishes)
    _tts_queues: dict = {}
    # Recent assistant texts to deduplicate repeated TTS within a short window
    _recent_assistant_texts: dict = {}
    
    @staticmethod
    async def twilio_to_deepgram(twilio_ws, audio_queues, streamsid_queue, session_metadata=None):
        """
        Receive audio from Twilio and queue for Deepgram
        
        Args:
            twilio_ws: Twilio WebSocket connection
            audio_queue: Queue for audio chunks
            streamsid_queue: Queue for stream ID
            session_metadata: Dict with phone_number and call_type
        """
        logger.info("Twilio receiver started")
        inbuffer = bytearray(b"")
        current_stream_id = None  # Store stream_id here
        session_metadata = session_metadata or {}
        
        async for message in twilio_ws:
            try:
                data = WebSocketHelper.parse_twilio_message(message)
                event = data.get("event")
                
                if event == "start":
                    # 📊 LATENCY TRACKING: Record call start time
                    start_time = time.time()
                    
                    # Extract all call information from Twilio
                    call_info = WebSocketHelper.extract_call_info(data)
                    stream_id = call_info["stream_sid"]
                    current_stream_id = stream_id  # Save it
                    streamsid_queue.put_nowait(stream_id)
                    
                    # Store start time for latency measurement
                    AudioStreamHandler._call_start_times[stream_id] = start_time
                    
                    # Prioritize session metadata for call_type (we set it correctly when creating session)
                    # Use Twilio data for phone_number (actual number being called/calling)
                    phone_number = call_info.get("phone_number") or session_metadata.get('phone_number')
                    call_type = session_metadata.get('call_type', 'inbound')  # Trust session metadata for call type
                    call_sid = call_info.get("call_sid")
                    
                    logger.info(f"📞 Call started | stream_id={stream_id} | call_sid={call_sid} | phone={phone_number} | type={call_type}")
                    
                    # Start collecting conversation data with metadata
                    db_logger.start_conversation(
                        stream_id,
                        phone_number=phone_number,
                        call_type=call_type,
                        call_sid=call_sid
                    )
                    
                elif event == "connected":
                    logger.info("Twilio connected")
                    
                elif event == "media":
                    media = data.get("media", {})
                    if media.get("track") == "inbound":
                        chunk = WebSocketHelper.decode_audio(media["payload"])
                        inbuffer.extend(chunk)
                        
                elif event == "stop":
                    logger.info("Call ended by Twilio")
                    # Save complete conversation to database (await to ensure it completes)
                    if current_stream_id:
                        await db_logger.save_conversation(current_stream_id)
                    break
                
                # Send buffered audio to one or more provider queues
                while len(inbuffer) >= AudioStreamHandler.BUFFER_SIZE:
                    chunk = inbuffer[:AudioStreamHandler.BUFFER_SIZE]
                    # audio_queues may be a single Queue or a list of Queues
                    queues = audio_queues if isinstance(audio_queues, (list, tuple)) else [audio_queues]
                    for q in queues:
                        try:
                            q.put_nowait(chunk)
                        except Exception:
                            # If a queue fails, log and continue
                            logger.warning("Failed to enqueue audio chunk to a provider queue")
                    inbuffer = inbuffer[AudioStreamHandler.BUFFER_SIZE:]
                    
            except Exception as e:
                logger.error("Error in Twilio receiver", error=str(e))
                break
    
    @staticmethod
    async def deepgram_to_twilio(deepgram_ws, twilio_ws, streamsid_queue, session_id: str, on_function_call):
        """
        Receive from Deepgram and send to Twilio
        
        Args:
            deepgram_ws: Deepgram WebSocket connection
            twilio_ws: Twilio WebSocket connection
            streamsid_queue: Queue for stream ID
            session_id: Session ID
            on_function_call: Callback for function calls
        """
        logger.info("Deepgram receiver started", session_id=session_id)
        stream_id = await streamsid_queue.get()
        
        # Track if we've sent first audio (for greeting latency measurement)
        first_audio_sent = False
        
        async for message in deepgram_ws:
            # 🔚 AUTO-HANGUP: Check if call should end after farewell (check on every loop)
            if stream_id in AudioStreamHandler._farewell_detected:
                last_activity = AudioStreamHandler._last_activity_time.get(stream_id)
                if last_activity:
                    idle_time = time.time() - last_activity
                    if idle_time > 2.0:  # Reduced from 5s to 2s for faster disconnect
                        logger.info(f"📞 AUTO-HANGUP: {idle_time:.1f}s of silence after farewell. Ending call gracefully.")
                        # Close connection to end call
                        break
            
            try:
                if isinstance(message, str):
                    # Text message (events, function calls)
                    import json
                    decoded = json.loads(message)
                    msg_type = decoded.get("type", "unknown")
                    
                    # Log important Deepgram events only
                    if msg_type == "UserStartedSpeaking":
                        await WebSocketHelper.send_clear(twilio_ws, stream_id)
                        # 📊 STT TIMING: Record when user started speaking
                        AudioStreamHandler._stt_start_times[stream_id] = time.time()
                        logger.info("🎤 User started speaking (barge-in + STT timing started)")
                    
                    elif msg_type == "UtteranceEnd":
                        role = decoded.get('role')
                        logger.info(f"UtteranceEnd: {role} finished speaking")
                        # If the user finished speaking, record timestamp to measure think latency
                        if role == 'user':
                            AudioStreamHandler._last_user_utterance_end_times[stream_id] = time.time()
                    
                    elif msg_type == "FunctionCallRequest":
                        function_name = decoded.get("function_name", "unknown")
                        logger.info(f"Function call: {function_name}")
                        
                        # Handle end_call explicitly for immediate hangup
                        if function_name == "end_call":
                            logger.info("📞 Tool requested hangup (end_call). Initiating graceful shutdown.")
                            AudioStreamHandler._farewell_detected[stream_id] = True
                            # Use a very short timeout since the intent is explicit
                            AudioStreamHandler._last_activity_time[stream_id] = time.time() - 1.0 # accelerated timeout check next loop
                        
                        await on_function_call(decoded, deepgram_ws, session_id, stream_id)
                    
                    elif msg_type == "ConversationText":
                        role = decoded.get("role", "unknown")
                        content = decoded.get("content", "")
                        logger.info(f"\n{'='*20}\n💬 {role.upper()}: {content}\n{'='*20}\n")

                        # 📊 LATENCY MEASUREMENTS
                        if role == 'user':
                            # STT LATENCY: User started speaking -> transcript ready
                            stt_start = AudioStreamHandler._stt_start_times.pop(stream_id, None)
                            if stt_start:
                                stt_latency_ms = (time.time() - stt_start) * 1000
                                logger.info(f"⏱️  STT LATENCY: {stt_latency_ms:.0f}ms (speech start → transcript)")
                            
                            # Mark LLM processing start
                            AudioStreamHandler._llm_start_times[stream_id] = time.time()
                            
                            # Track user activity for auto-hangup
                            AudioStreamHandler._last_activity_time[stream_id] = time.time()
                            
                            # Detect farewell phrases from user
                            farewell_phrases = ["goodbye", "bye", "see you", "thank you", "thanks", "cut the call", "hang up", "end call"]
                            if any(phrase in content.lower() for phrase in farewell_phrases):
                                logger.info(f"👋 Farewell detected from user")
                                AudioStreamHandler._farewell_detected[stream_id] = True
                        
                        elif role == 'assistant':
                            # LLM LATENCY: Transcript ready -> LLM response
                            llm_start = AudioStreamHandler._llm_start_times.pop(stream_id, None)
                            if llm_start:
                                llm_latency_ms = (time.time() - llm_start) * 1000
                                logger.info(f"⏱️  LLM LATENCY: {llm_latency_ms:.0f}ms (transcript → LLM response)")
                            
                            # THINK LATENCY: User utterance end -> assistant text (total pipeline)
                            last_end = AudioStreamHandler._last_user_utterance_end_times.pop(stream_id, None)
                            if last_end:
                                think_latency_ms = (time.time() - last_end) * 1000
                                logger.info(f"⏱️  TOTAL PIPELINE: {think_latency_ms:.0f}ms (user end → assistant text) 🚀")
                            
                            # Mark TTS processing start
                            AudioStreamHandler._tts_start_times[stream_id] = time.time()
                            
                            # Detect farewell from assistant
                            farewell_responses = ["goodbye", "bye", "take care", "have a great day", "enjoy your day", "alright"]
                            if any(phrase in content.lower() for phrase in farewell_responses):
                                logger.info(f"👋 Assistant farewell detected")
                        # Collect message in conversation (use stream_id, not session_id)
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_message(role, content)

                        # NOTE: Deepgram Voice Agent API already handles TTS internally.
                        # When Deepgram sends ConversationText for assistant, it also sends
                        # the corresponding binary audio. We do NOT need to call _speak_and_forward
                        # separately as that would cause the response to be spoken twice.
                        # The binary audio from Deepgram (handled in the else branch below) is
                        # already being forwarded to Twilio.
                        if role == 'assistant':
                            logger.info("Deepgram ConversationText (assistant) received — audio handled by Deepgram agent", session_id=session_id, stream_id=stream_id)
                            # No additional TTS needed - Deepgram sends audio via binary messages
                        # Note: Collector may not exist if message arrives after call ended - this is normal
                    
                    elif msg_type == "Warning":
                        # Log full warning message - this is critical for debugging
                        logger.warning(f"⚠️  Deepgram Warning: {json.dumps(decoded)}")
                        # Add warning to conversation collector
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_warning(decoded)

                    elif msg_type == "SettingsApplied":
                        logger.info("Deepgram event: SettingsApplied")
                        # If we recorded when config was sent, measure apply latency
                        sent_time = AudioStreamHandler._config_sent_times.pop(session_id, None)
                        if sent_time:
                            apply_latency_ms = (time.time() - sent_time) * 1000
                            logger.info(f"⏱️  CONFIG APPLY LATENCY: {apply_latency_ms:.0f}ms (config sent → settings applied)")
                    
                    elif msg_type == "Error":
                        # Log full error message
                        logger.error(f"❌ Deepgram Error: {json.dumps(decoded)}")
                        collector = db_logger.get_conversation(stream_id)
                        if collector:
                            collector.add_error(decoded)
                    
                    else:
                        # Log other event types to debug
                        logger.info(f"Deepgram event: {msg_type}")
                    
                else:
                    # Binary message (audio) - send to Twilio
                    try:
                        size = len(message) if hasattr(message, '__len__') else None
                    except Exception:
                        size = None
                    # Binary audio - send to Twilio (log suppressed for clarity)
                    await WebSocketHelper.send_media(twilio_ws, message, stream_id)
                    
                    # 📊 TTS LATENCY: First audio byte received
                    if stream_id in AudioStreamHandler._tts_start_times:
                        tts_start = AudioStreamHandler._tts_start_times.pop(stream_id)
                        tts_latency_ms = (time.time() - tts_start) * 1000
                        logger.info(f"⏱️  TTS LATENCY: {tts_latency_ms:.0f}ms (LLM text → first audio)")
                    
                    # 📊 LATENCY TRACKING: Measure greeting latency on first audio
                    if not first_audio_sent and stream_id in AudioStreamHandler._call_start_times:
                        first_audio_sent = True
                        start_time = AudioStreamHandler._call_start_times[stream_id]
                        greeting_latency = (time.time() - start_time) * 1000  # Convert to ms
                        logger.info(f"⏱️  GREETING LATENCY: {greeting_latency:.0f}ms (call answer → first audio)")
                        # Clean up timing data
                        del AudioStreamHandler._call_start_times[stream_id]
                    
            except Exception as e:
                logger.error("Error in Deepgram receiver", error=str(e), session_id=session_id)
                break
    
    @staticmethod
    async def send_to_deepgram(deepgram_ws, audio_queue):
        """
        Send audio from queue to Deepgram
        
        Args:
            deepgram_ws: Deepgram WebSocket connection
            audio_queue: Queue with audio chunks
        """
        logger.info("Audio sender started")
        
        while True:
            try:
                chunk = await audio_queue.get()
                try:
                    size = len(chunk) if hasattr(chunk, '__len__') else None
                except Exception:
                    size = None
                logger.debug("Sending audio chunk to Deepgram", bytes=size, ts=time.time())
                await deepgram_ws.send(chunk)
            except Exception as e:
                logger.error("Error sending audio to Deepgram", error=str(e))
                break

    @staticmethod
    def _extract_assistant_text_from_conversation(decoded: dict) -> str:
        """Extract assistant text from a Deepgram ConversationText payload.

        Handles content shapes that may be string, list of parts, or dict with 'parts'/'text'.
        """
        if not decoded:
            return ""
        content = decoded.get('content')
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get('text') or c.get('payload') or c.get('content')
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
                elif isinstance(c, str) and c.strip():
                    parts.append(c.strip())
            return "\n".join(parts)
        if isinstance(content, dict):
            parts = content.get('parts') or content.get('content')
            if isinstance(parts, list):
                texts = []
                for p in parts:
                    if isinstance(p, dict):
                        t = p.get('text') or p.get('payload') or p.get('content')
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
                if texts:
                    return "\n".join(texts)
            if isinstance(content.get('text'), str) and content.get('text').strip():
                return content.get('text').strip()
        return ""

    @staticmethod
    def _split_text_into_chunks(text: str, max_chars: int = 2000):
        """Split `text` into chunks of at most `max_chars` characters.

        Strategy:
        - Split by double-newline paragraphs first to preserve paragraph boundaries.
        - Greedy-fill chunks by adding paragraphs until the next para would overflow.
        - For paragraphs larger than `max_chars`, split at the last whitespace before the limit.
        """
        if not text:
            return []
        if len(text) <= max_chars:
            return [text]

        # Normalize newlines
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current = ""
        for para in paragraphs:
            if len(para) > max_chars:
                # Flush any current chunk first
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Split large paragraph greedily by whitespace
                start = 0
                while start < len(para):
                    end = min(start + max_chars, len(para))
                    if end < len(para):
                        # try to cut at last whitespace before end
                        split_at = para.rfind(' ', start, end)
                        if split_at <= start:
                            split_at = end
                        chunk = para[start:split_at]
                        chunks.append(chunk.strip())
                        start = split_at
                    else:
                        chunk = para[start:end]
                        chunks.append(chunk.strip())
                        break
            else:
                # Try to append paragraph to current chunk
                if not current:
                    current = para
                elif len(current) + 2 + len(para) <= max_chars:
                    current = current + "\n\n" + para
                else:
                    chunks.append(current.strip())
                    current = para
        if current:
            chunks.append(current.strip())
        return chunks

    @staticmethod
    async def _speak_and_forward(text: str, twilio_ws, stream_id: str, session_id: str):
        """Synthesize `text` using Deepgram's Speak websocket and forward audio to Twilio.

        Behaviors:
        - Process the initial `text` and then any queued assistant texts for `stream_id` sequentially.
        - Try websocket-based speak first; if not possible, fall back to REST TTS.
        - Ensure queuing works so new assistant messages are heard after the current TTS completes.
        """
        if not text:
            # If no initial text was provided, check the per-stream queue and use that first
            q0 = AudioStreamHandler._tts_queues.get(stream_id)
            if not q0:
                logger.debug("_speak_and_forward called with empty text and no queued items", session_id=session_id, stream_id=stream_id)
                return
            try:
                text = q0.get_nowait()
            except asyncio.QueueEmpty:
                logger.debug("_speak_and_forward: queue empty", session_id=session_id, stream_id=stream_id)
                return

        # Register start and ensure task entry cleaned up when finished
        try:
            logger.info("_speak_and_forward invoked", session_id=session_id, stream_id=stream_id)
            import websockets
            from app.core.config import settings
            api_key = settings.DEEPGRAM_API_KEY
            if not api_key:
                logger.error("Deepgram API key not configured; cannot perform TTS", session_id=session_id)
                return

            speak_model = getattr(settings, 'DEEPGRAM_SPEAK_MODEL', None) or 'aura-2-thalia-en'
            attempts = [
                ("mulaw", 8000, speak_model),
                ("linear16", 24000, speak_model),
            ]

            # Process initial text and any queued texts sequentially
            while True:
                handled = False
                connected = False

                for encoding, sample_rate, model in attempts:
                    # Try header-based authorization first (Authorization: Token <key>)
                    uri_no_token = f"wss://api.deepgram.com/v1/speak?model={model}&encoding={encoding}&sample_rate={sample_rate}"
                    headers = [("Authorization", f"Token {api_key}")]
                    logger.info("Trying TTS speak connection (header)", session_id=session_id, stream_id=stream_id, uri=uri_no_token)
                    try:
                        async with websockets.connect(uri_no_token, extra_headers=headers) as ws:
                            connected = True
                            # Send Speak then Flush to request audio
                            await ws.send(json.dumps({"type": "Speak", "text": text}))
                            await ws.send(json.dumps({"type": "Flush"}))

                            flushed = False
                            last_binary = time.time()
                            # Listen for messages: text (events) or bytes (audio)
                            while True:
                                try:
                                    msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                                except asyncio.TimeoutError:
                                    if flushed and (time.time() - last_binary) > 2.0:
                                        logger.info("TTS finished (timeout after flush)", session_id=session_id, stream_id=stream_id)
                                        break
                                    logger.debug("TTS recv timeout, continuing", session_id=session_id, stream_id=stream_id)
                                    continue
                                except Exception as e:
                                    err = str(e)
                                    logger.error("TTS websocket closed or error (header)", error=err, session_id=session_id)
                                    # If the websockets implementation doesn't support extra_headers
                                    # (some event loop adapters don't), try token query param fallback
                                    if "extra_headers" in err or "unexpected keyword argument 'extra_headers'" in err:
                                        uri_with_token = f"wss://api.deepgram.com/v1/speak?token={api_key}&model={model}&encoding={encoding}&sample_rate={sample_rate}"
                                        logger.info("Trying TTS speak connection (token fallback due to header unsupported)", session_id=session_id, stream_id=stream_id, uri=uri_with_token)
                                        try:
                                            async with websockets.connect(uri_with_token) as ws:
                                                connected = True
                                                await ws.send(json.dumps({"type": "Speak", "text": text}))
                                                await ws.send(json.dumps({"type": "Flush"}))

                                                flushed = False
                                                last_binary = time.time()
                                                while True:
                                                    try:
                                                        msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                                                    except asyncio.TimeoutError:
                                                        if flushed and (time.time() - last_binary) > 2.0:
                                                            logger.info("TTS finished (timeout after flush)", session_id=session_id, stream_id=stream_id)
                                                            break
                                                        logger.debug("TTS recv timeout, continuing", session_id=session_id, stream_id=stream_id)
                                                        continue
                                                    except Exception as e2:
                                                        logger.error("TTS websocket closed or error (token fallback)", error=str(e2), session_id=session_id)
                                                        break

                                                    if isinstance(msg, str):
                                                        try:
                                                            j = json.loads(msg)
                                                            mtype = j.get('type')
                                                            logger.info("TTS event", session_id=session_id, stream_id=stream_id, type=mtype, preview=str(j)[:200])
                                                            if mtype in ("Flushed", "Cleared"):
                                                                flushed = True
                                                                continue
                                                        except Exception:
                                                            logger.debug("Non-json TTS message", session_id=session_id)
                                                    else:
                                                        # Binary chunk
                                                        last_binary = time.time()
                                                        try:
                                                            size = len(msg)
                                                        except Exception:
                                                            size = None
                                                        logger.info("TTS -> Twilio binary audio", session_id=session_id, stream_id=stream_id, bytes=size)
                                                        ok = await WebSocketHelper.send_media(twilio_ws, msg, stream_id)
                                                        if not ok:
                                                            logger.warning("Failed to forward TTS audio to Twilio", session_id=session_id, stream_id=stream_id)
                                                # End inner loop — one successful encoding handled
                                                handled = True
                                                break
                                        except websockets.exceptions.InvalidStatusCode as e2:
                                            logger.warning("TTS handshake rejected (token fallback)", session_id=session_id, encoding=encoding, sample_rate=sample_rate, model=model, status=getattr(e2, 'status_code', None), error=str(e2))
                                            continue
                                        except Exception as e2:
                                            logger.error("Unexpected error during TTS attempt (token fallback)", error=str(e2), session_id=session_id)
                                            continue
                                    else:
                                        break

                                if isinstance(msg, str):
                                    try:
                                        j = json.loads(msg)
                                        mtype = j.get('type')
                                        logger.info("TTS event", session_id=session_id, stream_id=stream_id, type=mtype, preview=str(j)[:200])
                                        if mtype in ("Flushed", "Cleared"):
                                            flushed = True
                                            continue
                                    except Exception:
                                        logger.debug("Non-json TTS message", session_id=session_id)
                                else:
                                    # Binary chunk
                                    last_binary = time.time()
                                    try:
                                        size = len(msg)
                                    except Exception:
                                        size = None
                                    logger.info("TTS -> Twilio binary audio", session_id=session_id, stream_id=stream_id, bytes=size)
                                    ok = await WebSocketHelper.send_media(twilio_ws, msg, stream_id)
                                    if not ok:
                                        logger.warning("Failed to forward TTS audio to Twilio", session_id=session_id, stream_id=stream_id)
                            # End inner loop — one successful encoding handled
                            handled = True
                            break
                    except websockets.exceptions.InvalidStatusCode as e:
                        logger.warning("TTS handshake rejected (header)", session_id=session_id, encoding=encoding, sample_rate=sample_rate, model=model, status=getattr(e, 'status_code', None), error=str(e))
                        # Fallback: try token query param style
                        uri_with_token = f"wss://api.deepgram.com/v1/speak?token={api_key}&model={model}&encoding={encoding}&sample_rate={sample_rate}"
                        logger.info("Trying TTS speak connection (token fallback)", session_id=session_id, stream_id=stream_id, uri=uri_with_token)
                        try:
                            async with websockets.connect(uri_with_token) as ws:
                                connected = True
                                await ws.send(json.dumps({"type": "Speak", "text": text}))
                                await ws.send(json.dumps({"type": "Flush"}))

                                flushed = False
                                last_binary = time.time()
                                while True:
                                    try:
                                        msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                                    except asyncio.TimeoutError:
                                        if flushed and (time.time() - last_binary) > 2.0:
                                            logger.info("TTS finished (timeout after flush)", session_id=session_id, stream_id=stream_id)
                                            break
                                        logger.debug("TTS recv timeout, continuing", session_id=session_id, stream_id=stream_id)
                                        continue
                                    except Exception as e:
                                        logger.error("TTS websocket closed or error (token fallback)", error=str(e), session_id=session_id)
                                        break

                                    if isinstance(msg, str):
                                        try:
                                            j = json.loads(msg)
                                            mtype = j.get('type')
                                            logger.info("TTS event", session_id=session_id, stream_id=stream_id, type=mtype, preview=str(j)[:200])
                                            if mtype in ("Flushed", "Cleared"):
                                                flushed = True
                                                continue
                                        except Exception:
                                            logger.debug("Non-json TTS message", session_id=session_id)
                                    else:
                                        # Binary chunk
                                        last_binary = time.time()
                                        try:
                                            size = len(msg)
                                        except Exception:
                                            size = None
                                        logger.info("TTS -> Twilio binary audio", session_id=session_id, stream_id=stream_id, bytes=size)
                                        ok = await WebSocketHelper.send_media(twilio_ws, msg, stream_id)
                                        if not ok:
                                            logger.warning("Failed to forward TTS audio to Twilio", session_id=session_id, stream_id=stream_id)
                                # End inner loop — one successful encoding handled
                                handled = True
                                break
                        except websockets.exceptions.InvalidStatusCode as e2:
                            logger.warning("TTS handshake rejected (token fallback)", session_id=session_id, encoding=encoding, sample_rate=sample_rate, model=model, status=getattr(e2, 'status_code', None), error=str(e2))
                            continue
                        except Exception as e2:
                            logger.error("Unexpected error during TTS attempt (token fallback)", error=str(e2), session_id=session_id)
                            continue
                    except Exception as e:
                        logger.error("Unexpected error during TTS attempt (header)", error=str(e), session_id=session_id)
                        continue

                if not handled and not connected:
                    logger.warning("All TTS handshake attempts failed; attempting REST TTS fallback", session_id=session_id)
                    # Try REST TTS fallback to avoid dependency on websocket handshake
                    try:
                        import httpx
                        rest_url = f"https://api.deepgram.com/v1/speak?model={model}&encoding=mulaw&sample_rate=8000"
                        headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
                        logger.info("Attempting REST TTS fallback", session_id=session_id, uri=rest_url)

                        MAX_TTS_CHARS = getattr(settings, 'DEEPGRAM_SPEAK_MAX_CHARS', 2000)

                        async def _post_and_stream(client, text_to_send, chunk_index=None, total_chunks=None):
                            body = {"text": text_to_send}
                            try:
                                resp = await client.post(rest_url, json=body, headers=headers)
                            except Exception as e:
                                logger.error("REST TTS chunk request failed", error=str(e), session_id=session_id, chunk_index=chunk_index)
                                return False, getattr(e, 'response', None)

                            if resp.status_code != 200:
                                logger.error("REST TTS chunk failed", session_id=session_id, chunk_index=chunk_index, status=resp.status_code, preview=resp.text[:500])
                                return False, resp

                            # Stream bytes to Twilio in frame-sized chunks
                            async for chunk in resp.aiter_bytes(chunk_size=160):
                                if not chunk:
                                    continue
                                ok = await WebSocketHelper.send_media(twilio_ws, chunk, stream_id)
                                if not ok:
                                    logger.warning("Failed to forward REST TTS chunk to Twilio", session_id=session_id, chunk_index=chunk_index)
                                    return False, resp
                            logger.info("REST TTS chunk forwarded", session_id=session_id, chunk_index=chunk_index, total_chunks=total_chunks)
                            return True, resp

                        async with httpx.AsyncClient(timeout=60.0) as client:
                            # Pre-split long texts to avoid Deepgram 413 (max 2000 chars)
                            if len(text) > MAX_TTS_CHARS:
                                chunks = AudioStreamHandler._split_text_into_chunks(text, MAX_TTS_CHARS)
                                logger.warning("TTS input exceeds max chars; splitting into chunks", session_id=session_id, stream_id=stream_id, count=len(chunks))
                                for idx, chunk_text in enumerate(chunks, start=1):
                                    logger.info("Sending TTS chunk", session_id=session_id, stream_id=stream_id, index=idx, total=len(chunks), chars=len(chunk_text), preview=chunk_text[:200])
                                    success, resp = await _post_and_stream(client, chunk_text, chunk_index=idx, total_chunks=len(chunks))
                                    if not success:
                                        # If 413 returned for a chunk, try splitting that chunk smaller and attempt again
                                        status = getattr(resp, 'status_code', None)
                                        if status == 413:
                                            logger.warning("Chunk too large despite split - further splitting", session_id=session_id, stream_id=stream_id, chunk_index=idx)
                                            subchunks = AudioStreamHandler._split_text_into_chunks(chunk_text, max_chars=MAX_TTS_CHARS // 2)
                                            for sidx, stext in enumerate(subchunks, start=1):
                                                logger.info("Sending subchunk", session_id=session_id, stream_id=stream_id, chunk_index=idx, sub_index=sidx, chars=len(stext))
                                                ok, _ = await _post_and_stream(client, stext, chunk_index=f"{idx}.{sidx}", total_chunks=f"{len(chunks)}+{len(subchunks)}")
                                                if not ok:
                                                    logger.error("Failed to deliver TTS subchunk", session_id=session_id, stream_id=stream_id, chunk_index=f"{idx}.{sidx}")
                                                    # Give up on this chunk and continue to next
                                                    break
                                        else:
                                            logger.error("Failed to deliver TTS chunk - aborting remaining chunks", session_id=session_id, stream_id=stream_id, chunk_index=idx)
                                            break
                                    # small gap between chunk requests to avoid rate issues
                                    await asyncio.sleep(0.06)
                                logger.info("REST TTS fallback completed; forwarded audio to Twilio (chunked)", session_id=session_id)
                                handled = True
                                # continue to check queued items and process them next

                            # Try single request first
                            success, resp = await _post_and_stream(client, text, chunk_index=1, total_chunks=1)
                            if success:
                                logger.info("REST TTS fallback completed; forwarded audio to Twilio", session_id=session_id)
                                handled = True
                                # continue to check queued items and process them next

                            # If we got a 413 for single long response, split and retry
                            status = getattr(resp, 'status_code', None)
                            if status == 413:
                                logger.warning("REST TTS single request rejected with 413 - splitting text", session_id=session_id)
                                chunks = AudioStreamHandler._split_text_into_chunks(text, MAX_TTS_CHARS)
                                for idx, chunk_text in enumerate(chunks, start=1):
                                    logger.info("Sending TTS chunk after 413", session_id=session_id, stream_id=stream_id, index=idx, total=len(chunks), chars=len(chunk_text))
                                    ok, _ = await _post_and_stream(client, chunk_text, chunk_index=idx, total_chunks=len(chunks))
                                    if not ok:
                                        logger.error("Failed to deliver TTS chunk after 413", session_id=session_id, stream_id=stream_id, chunk_index=idx)
                                        break
                                    await asyncio.sleep(0.06)
                                logger.info("REST TTS fallback completed; forwarded audio to Twilio (after 413)", session_id=session_id)
                                handled = True
                                # continue to check queued items and process them next

                            # Otherwise, we already logged the failure in _post_and_stream
                            return
                    except Exception as e:
                        logger.error("REST TTS fallback failed", error=str(e), session_id=session_id)
                        return

                # After attempting all transport methods, if we handled this text we should
                # check whether there are queued texts to process next. If not, exit the
                # loop and finish the TTS task.
                q = AudioStreamHandler._tts_queues.get(stream_id)
                next_text = None
                if q:
                    try:
                        next_text = q.get_nowait()
                    except Exception:
                        next_text = None
                if next_text:
                    logger.info("Dequeued next TTS for stream — continuing", session_id=session_id, stream_id=stream_id)
                    text = next_text
                    # continue to process next queued text
                    continue

                # No queued items — clean up queue reference if present and finish
                if q and getattr(q, 'empty', None) and q.empty():
                    try:
                        del AudioStreamHandler._tts_queues[stream_id]
                    except Exception:
                        pass
                break

        except Exception as e:
            logger.error("Error in _speak_and_forward", error=str(e), session_id=session_id)
        finally:
            # Ensure the task reference is removed so new TTS can start cleanly
            try:
                AudioStreamHandler._tts_tasks.pop(stream_id, None)
            except Exception:
                pass
            logger.info("_speak_and_forward finished/cleaned up", session_id=session_id, stream_id=stream_id)
    @staticmethod
    async def google_to_deepgram(google_ws, deepgram_ws, streamsid_queue, session_id: str, on_function_call):
        """
        Bridge messages from Google adapter to Deepgram so assistant text
        produced by the Google adapter (Gemini responses) are forwarded
        to Deepgram for TTS.
        """
        logger.info("Google -> Deepgram bridge started", session_id=session_id)
        stream_id = await streamsid_queue.get()

        async for message in google_ws:
            try:
                logger.info(f"Google bridge received message type: {type(message)}, length: {len(message) if hasattr(message, '__len__') else 'N/A'} | preview: {str(message)[:200]}...")
                if isinstance(message, str):
                    import json
                    decoded = json.loads(message)
                    msg_type = decoded.get("type", "unknown")
                    if msg_type == "ConversationText":
                        role = decoded.get("role", "unknown")
                        # Forward assistant and function messages to Deepgram
                        if role in ("assistant", "system"):
                            try:
                                payload = json.dumps(decoded)
                            except Exception:
                                payload = str(decoded)
                            try:
                                size = len(payload)
                            except Exception:
                                size = None
                            preview = (payload[:1000] + '...') if isinstance(payload, str) and len(payload) > 1000 else payload
                            logger.info("Google -> Deepgram forward", session_id=session_id, stream_id=stream_id, role=role, bytes=size, preview=preview, ts=time.time())
                            try:
                                await deepgram_ws.send(payload)
                            except Exception as e:
                                logger.error("Failed to forward Google assistant message to Deepgram", error=str(e))
                        # If Google produced a function call, hand it off
                        # to the same function handler used by Deepgram messages
                    elif msg_type == "FunctionCallRequest":
                        await on_function_call(decoded, deepgram_ws, session_id, stream_id)
                else:
                    # Google adapter shouldn't produce binary audio here; ignore
                    pass
            except Exception as e:
                logger.error("Error in Google->Deepgram bridge", error=str(e), session_id=session_id)
                break
