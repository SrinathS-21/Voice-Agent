"""
Deepgram Service
Handles Deepgram API connections with a robust async context manager.

This implementation wraps `websockets.connect()` in an `asynccontextmanager`
and supports environments where `websockets.connect()` returns either an
awaitable (common) or a sync adapter object (some packaged variants). Callers
must be able to use `async with DeepgramService.connect(...) as ws:`.
"""

import websockets
import inspect
import asyncio
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import ExternalServiceException
from app.core.logging import get_logger

logger = get_logger(__name__)


class DeepgramService:
    """Service for Deepgram API interactions"""

    @staticmethod
    def connect(agent_metadata: dict | None = None):
        """
        Return an async context manager that yields a connected websocket client.
        """
        api_key = settings.DEEPGRAM_API_KEY
        if not api_key:
            raise ExternalServiceException("Deepgram", "API key not configured")

        logger.debug("Preparing Deepgram websocket connection")

        extra_headers = {}
        if agent_metadata and isinstance(agent_metadata, dict):
            speak = agent_metadata.get("speak") or (agent_metadata.get("agent_config") or {}).get("speak")
            if isinstance(speak, dict):
                voice = speak.get("voice")
                if voice:
                    extra_headers["X-Agent-Voice"] = str(voice)
            agent_id = agent_metadata.get("id")
            if agent_id:
                extra_headers["X-Agent-ID"] = str(agent_id)

        uri = "wss://agent.deepgram.com/v1/agent/converse"
        subprotocols = ["token", api_key]

        @asynccontextmanager
        async def _cm():
            # Call websockets.connect; avoid passing extra headers directly to
            # maintain compatibility with different websockets versions.
            try:
                conn_obj = websockets.connect(uri, subprotocols=subprotocols)
            except TypeError:
                # Fallback if the signature differs
                conn_obj = websockets.connect(uri)

            if inspect.isawaitable(conn_obj):
                ws = await conn_obj
                try:
                    yield ws
                finally:
                    try:
                        await ws.close()
                    except Exception:
                        logger.debug("Error closing Deepgram websocket", exc_info=True)
            else:
                loop = asyncio.get_event_loop()
                # enter the sync adapter in a thread
                ws = await loop.run_in_executor(None, lambda: conn_obj.__enter__())
                try:
                    yield ws
                finally:
                    await loop.run_in_executor(None, lambda: conn_obj.__exit__(None, None, None))

        return _cm()
