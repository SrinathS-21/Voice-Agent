from fastapi import APIRouter, HTTPException
from app.schemas.config_schemas import VoiceAgentConfigSchema
from app.services.session_service import get_session_service
from app.models.session import CallType
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/create")
async def create_assistant(config: VoiceAgentConfigSchema, tenant_id: int | None = None):
    """Create a session for the provided assistant configuration.

    This mirrors the VAPI `assistant.create` behavior by creating a live session
    from an assistant config and returning the websocket URL and session id.
    """
    try:
        service = get_session_service()
        session = await service.create_session(config=config, call_type=CallType.INBOUND, tenant_id=tenant_id)
        websocket_url = f"{getattr(settings, 'WEBSOCKET_URL', '/voice')}/voice/{session.session_id}" if getattr(settings, 'WEBSOCKET_URL', None) else f"/voice/{session.session_id}"
        # Return minimal session info (caller can fetch full via /sessions)
        return {
            "session_id": session.session_id,
            "websocket_url": websocket_url,
            "status": session.status.value,
            "created_at": session.created_at.isoformat()
        }
    except Exception as e:
        logger.error("Failed to create assistant session", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
