"""
Gemini Client

Simple HTTP client to call Gemini 2.5 Flash via a configured REST endpoint
using an API key. This is intentionally generic: the exact endpoint and
request shape can be adjusted via `settings` to match the Gemini API you
have access to.

Functions:
- `generate_text(prompt, **opts)` -> returns parsed JSON response

Notes:
- Requires `httpx` (already in `requirements.txt`).
- Configure `GEMINI_API_KEY` and optionally `GEMINI_API_URL` in your env or
  `app.core.config.settings`.
"""

import os
import json
import httpx
import os as _os
try:
    import google.auth
    from google.auth.transport.requests import Request as GoogleAuthRequest
except Exception:
    google = None
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


DEFAULT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
DEFAULT_BASE = "https://generativelanguage.googleapis.com"


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        # allow api_key to be None and fall back to ADC bearer tokens
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        self.api_url = api_url or getattr(settings, "GEMINI_API_URL", None) or os.getenv("GEMINI_API_URL") or DEFAULT_URL
        # This client intentionally prefers per-model generate endpoints
        # (e.g. /v1beta/models/gemini-2.5-flash:generateContent). Avoid
        # runtime model discovery and top-level RPC probing which can cause
        # 404s in some environments.

    async def generate_text(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024, **kwargs) -> Dict[str, Any]:
        """Call Gemini to generate text.

        This method uses a generic request body and returns the provider
        response as a parsed JSON dictionary. Adjust `body` to match your
        Gemini API contract if it differs.
        """
        headers = {
            "Content-Type": "application/json",
        }

        # Authentication: prefer API key if provided (uses x-goog-api-key),
        # otherwise attempt Application Default Credentials to obtain an
        # OAuth2 access token.
        if self.api_key:
            # Some Google endpoints accept API key in query param; use header
            # to avoid changing the URL in existing callers.
            headers["x-goog-api-key"] = self.api_key
        else:
            # Try to obtain ADC and refresh to get access token
            try:
                if google is None:
                    raise RuntimeError("google-auth not available; install google-auth or set GEMINI_API_KEY")
                creds, project = google.auth.default(scopes=("https://www.googleapis.com/auth/cloud-platform",))
                creds.refresh(GoogleAuthRequest())
                token = creds.token
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logger.error("Gemini auth error: provide GEMINI_API_KEY or configure Application Default Credentials", error=str(e))
                raise RuntimeError("Gemini auth not configured: set GEMINI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")

        # Validate prompt
        if not prompt or not prompt.strip():
            raise ValueError("Empty prompt passed to Gemini client")

        # We'll decide which request body to build after resolving the configured URL.
        prompt_text = prompt

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Always call the configured URL. Prefer per-model generate endpoints
            # (e.g. /v1beta/models/gemini-2.5-flash:generateContent). If a top-level
            # RPC endpoint is configured, fall back to the default per-model URL.
            generate_url = self.api_url
            url_str = str(generate_url)
            if "/v1beta/models:" in url_str and "/v1beta/models/" not in url_str:
                # configured URL looks like a top-level RPC; use explicit per-model default
                generate_url = DEFAULT_URL
                url_str = generate_url
            # Two canonical body shapes used by the API:
            # - generateText / top-level generateText: {"prompt": {"text": ...}, "maxOutputTokens": ...}
            # - generateContent / per-model generateContent: {"contents": [{"parts":[{"text": ...}]}]}
            # For per-model endpoints the API may reject unknown top-level params
            # like `temperature` or `maxOutputTokens`. Build a minimal `contents`
            # body for per-model endpoints and, if a max token limit was requested,
            # prepend a brief instruction to the prompt to encourage shorter replies.

            # Apply any kwargs to prompt-level shapes only
            prompt_body = {"prompt": {"text": prompt_text}, "temperature": temperature, "maxOutputTokens": max_tokens}
            prompt_body = {**prompt_body, **kwargs}

            if ":generateContent" in url_str:
                # Per-model generateContent endpoints accept a `generationConfig`
                # object for generation parameters (temperature, maxOutputTokens,
                # topP, topK, stopSequences, etc.). Construct that config from
                # the explicit args and any supported kwargs to avoid sending
                # unknown top-level fields which the API rejects.
                gen_keys = (
                    'maxOutputTokens', 'temperature', 'topP', 'topK', 'candidateCount',
                    'stopSequences', 'responseMimeType', 'presencePenalty', 'frequencyPenalty', 'seed'
                )
                gen_conf = {}
                # Seed base values
                if max_tokens is not None:
                    gen_conf['maxOutputTokens'] = int(max_tokens)
                if temperature is not None:
                    gen_conf['temperature'] = float(temperature)
                # Pull supported keys from kwargs when present
                for k in gen_keys:
                    # kwargs may use camelCase or snake_case; accept both simple names
                    if k in kwargs:
                        gen_conf[k] = kwargs.get(k)

                contents_body = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": gen_conf}
                final_body = contents_body
            else:
                final_body = prompt_body

            # Log the actual request body we're sending (trim large content)
            try:
                body_preview = json.dumps(final_body) if isinstance(final_body, (dict, list)) else str(final_body)
                if len(body_preview) > 1000:
                    body_preview = body_preview[:1000] + "..."
                logger.info("Calling Gemini generate (per-model only)", url=generate_url, body_preview=body_preview)
            except Exception:
                logger.info("Calling Gemini generate (per-model only)", url=generate_url)

            resp = await client.post(generate_url, json=final_body, headers=headers)
            text = resp.text
            try:
                data = resp.json()
            except Exception:
                logger.error("Gemini response not JSON", status_code=resp.status_code, body=text)
                if resp.status_code == 404:
                    return {"text": "[Gemini unavailable: model/endpoint not found]"}
                raise

            if resp.status_code >= 400:
                # Log request/response for debugging
                try:
                    resp_preview = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
                except Exception:
                    resp_preview = str(data)
                logger.error("Gemini API error", status_code=resp.status_code, request_body=(body_preview if 'body_preview' in locals() else None), body=resp_preview)
                # 400: bad request (shape/auth); surface message
                raise RuntimeError(f"Gemini API error: {resp.status_code}")

            # Log response size/summary for visibility
            try:
                resp_text_preview = (resp.text[:200] + '...') if len(resp.text) > 200 else resp.text
                logger.info("Gemini response received", status_code=resp.status_code, text_preview=resp_text_preview)
            except Exception:
                pass

            logger.info("Gemini request succeeded")
            return data


from functools import lru_cache


@lru_cache()
def get_gemini_client() -> GeminiClient:
    """Return a cached GeminiClient instance.

    This lazy initializer ensures settings/.env are read before the
    client is created and avoids raising at import time when the key
    might not be available in the process environment.
    """
    return GeminiClient()
