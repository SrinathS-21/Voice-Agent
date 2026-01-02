"""
Provider Service
Dispatches connections to the configured provider (Deepgram or Google)

This module provides a small compatibility layer so existing code can
call `ProviderService.connect()` and receive an async context manager
that yields an object compatible with the current websocket-based
usage (supports `await conn.send(...)` and `async for msg in conn`).

The Google adapter here is a scaffold — it provides the required
interface and queue plumbing. We'll replace the scaffold internals
with real Google Speech-to-Text (streaming) + Vertex AI (Gemini)
integration next.
"""

from app.core.logging import get_logger
from app.core.exceptions import ExternalServiceException

from websocket_server.services.deepgram_service import DeepgramService
from websocket_server.services.speech_service import GoogleSpeechService

logger = get_logger(__name__)


class ProviderService:
    @staticmethod
    def connect(provider_type: str = "deepgram", agent_metadata: dict | None = None):
        """Return an async context manager for the chosen provider.

        provider_type: 'deepgram' or 'google'
        """
        if provider_type == "deepgram":
            return DeepgramService.connect(agent_metadata=agent_metadata)
        elif provider_type == "google":
            return GoogleSpeechService.connect(agent_metadata=agent_metadata)
        else:
            raise ExternalServiceException("ProviderService", f"Unknown provider type: {provider_type}")
