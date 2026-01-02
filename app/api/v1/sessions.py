"""
Session Routes
API endpoints for session management
"""

import os
import json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.schemas.session_schemas import (
    SessionCreateRequest,
    SessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionListItem
)
from app.schemas.call_schemas import OutboundCallRequest, OutboundCallResponse
from pydantic import BaseModel
from fastapi import Body
from app.services.session_service import get_session_service, SessionService
from app.models.session import CallType, Session, SessionStatus
from app.core.config import settings
from app.core.exceptions import SessionNotFoundException, SessionExpiredException, VoiceAgentException
from app.core.logging import get_logger
from app.session_cache import set_session_cache
from app.core.convex_client import get_convex_client

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])

# Convex is the primary database - PostgreSQL migration complete
USE_CONVEX = os.getenv("USE_CONVEX", "true").lower() == "true"



@router.post("/create", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest):
    """
    Create a new voice agent session with custom configuration
    
    This endpoint receives configuration from the frontend and creates a
    dynamic voice agent session with custom business logic, prompts, and functions.
    """
    try:
        service = get_session_service()
        
        # Create session
        session = await service.create_session(
            config=request.config,
            call_type=CallType(request.call_type),
            phone_number=request.phone_number
        )
        
        # --- CACHE SESSION DATA ---
        set_session_cache(session.session_id, {
            "config": session.config,
            "details": {
                "session_id": session.session_id,
                "status": session.status.value,
                "call_type": session.call_type.value if session.call_type else "inbound",
                "phone_number": session.metadata.get("phone_number", "unknown"),
                "business": session.business_info,
                "metadata": session.metadata,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }
        })
        
        # Generate WebSocket URL
        websocket_url = f"{settings.BASE_WEBSOCKET_URL}/voice/{session.session_id}"
        
        logger.info(
            "Session created via API",
            session_id=session.session_id,
            business=request.config.business.name
        )
        
        return SessionResponse(
            session_id=session.session_id,
            websocket_url=websocket_url,
            status=session.status.value,
            created_at=session.created_at.isoformat(),
            expires_at=session.expires_at.isoformat() if session.expires_at else None,
            config_summary={
                "business": request.config.business.name,
                "language": request.config.language,
                "functions_available": len(request.config.functions)
            }
        )
    
    except VoiceAgentException as e:
        logger.error("Failed to create session", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error creating session", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


class CreateFromNumberRequest(BaseModel):
    phone_number: str
    call_type: str = "outbound"


@router.post("/create-from-number", response_model=SessionResponse, status_code=201)
async def create_session_from_number(payload: CreateFromNumberRequest = Body(...)):
    """Create a session using the PhoneNumberConfig for the provided phone number

    This is useful for outbound calls where each Twilio number has a pre-configured
    VoiceAgentConfig (stored in phone_number_configs.config_json). It will create
    a session with that config and return the websocket URL.
    """
    config_json_data = None
    tenant_id = None
    agent_id = None
    
    # Lookup phone number config
    if USE_CONVEX:
        client = get_convex_client()
        config_result = await client.query("phoneConfigs:getByPhoneNumber", {
            "phoneNumber": payload.phone_number
        })
        
        if not config_result:
            raise HTTPException(status_code=404, detail="Phone configuration not found")
        
        # Parse config JSON from Convex
        config_json_str = config_result.get("configJson", "{}")
        if isinstance(config_json_str, str):
            try:
                config_json_data = json.loads(config_json_str)
            except json.JSONDecodeError:
                config_json_data = {}
        else:
            config_json_data = config_json_str
        
        agent_id = config_result.get("agentId")
        organization_id = config_result.get("organizationId")  # Get organization from phone config
        # Convex uses organizationId string, no tenant_id int for now
        tenant_id = None
    else:
        # Legacy fallback (deprecated - use Convex)
        organization_id = None
        async with AsyncSessionLocal() as db:
            q = select(PhoneNumberConfig).where(PhoneNumberConfig.phone_number == payload.phone_number)
            res = await db.execute(q)
            config_row = res.scalar_one_or_none()

        if not config_row:
            raise HTTPException(status_code=404, detail="Phone configuration not found")
        
        config_json_data = config_row.config_json
        tenant_id = getattr(config_row, 'tenant_id', None)
        agent_id = getattr(config_row, 'agent_id', None)

    # Parse config JSON into VoiceAgentConfigSchema. If the phone's JSON is invalid,
    # fall back to any bound Agent's config (and merge phone config on top when present).
    from app.schemas.config_schemas import VoiceAgentConfigSchema
    try:
        config_schema = VoiceAgentConfigSchema.parse_obj(config_json_data)
    except Exception as e:
        logger.info("Phone config JSON failed schema validation, attempting agent fallback", phone_number=payload.phone_number)
        # If this phone is bound to an Agent, try to use that agent's stored config
        agent_config_merged = None
        if agent_id:
            # Agent lookup (legacy path)
            async with AsyncSessionLocal() as db:
                q = select(Agent).where(Agent.id == agent_id)
                res = await db.execute(q)
                agent_row = res.scalar_one_or_none()
            if agent_row and agent_row.config:
                # Merge phone config (if dict) on top of agent config so per-number overrides apply
                merged = {}
                if isinstance(agent_row.config, dict):
                    merged.update(agent_row.config)
                if isinstance(config_json_data, dict):
                    merged.update(config_json_data)
                agent_config_merged = merged

        if not agent_config_merged:
            logger.error("Invalid phone config JSON and no valid bound agent config found", error=str(e), phone_number=payload.phone_number)
            raise HTTPException(status_code=400, detail="Invalid phone configuration JSON")

        try:
            config_schema = VoiceAgentConfigSchema.parse_obj(agent_config_merged)
        except Exception as e2:
            logger.error("Agent config JSON also invalid", error=str(e2), phone_number=payload.phone_number)
            raise HTTPException(status_code=400, detail="Invalid phone configuration JSON")

    # Create session
    try:
        service = get_session_service()
        session = await service.create_session(
            config_schema,
            call_type=CallType(payload.call_type),
            phone_number=payload.phone_number,
            tenant_id=tenant_id,
            organization_id=organization_id
        )

        # Cache session
        set_session_cache(session.session_id, {
            "config": session.config,
            "details": {
                "session_id": session.session_id,
                "status": session.status.value,
                "call_type": session.call_type.value if session.call_type else "outbound",
                "phone_number": session.metadata.get("phone_number", "unknown"),
                "business": session.business_info,
                "tenant_id": session.tenant_id,
                "organization_id": session.organization_id,  # Include org ID for dynamic functions
                "metadata": session.metadata,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }
        })

        websocket_url = f"{settings.BASE_WEBSOCKET_URL}/voice/{session.session_id}"

        return SessionResponse(
            session_id=session.session_id,
            websocket_url=websocket_url,
            status=session.status.value,
            created_at=session.created_at.isoformat(),
            expires_at=session.expires_at.isoformat() if session.expires_at else None,
            config_summary={
                "business": config_schema.business.name,
                "language": config_schema.language,
                "functions_available": len(config_schema.functions)
            }
        )
    except Exception as e:
        logger.error("Failed to create session from phone config", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outbound", response_model=OutboundCallResponse)
async def make_outbound_call(payload: OutboundCallRequest):
    """Create a session for the phone config's number and place an outbound Twilio call

    This endpoint simplifies the UI flow: user selects a configured Twilio number, selects a destination,
    and the backend creates the session and places the call.
    """
    # Create session from the Twilio 'from' number
    try:
        create_payload = CreateFromNumberRequest(phone_number=payload.from_number, call_type="outbound")
        session_response = await create_session_from_number(create_payload)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("Failed to create session for outbound call", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # Place outbound call using Twilio
    call_sid = None
    call_placed = False
    message = None
    try:
        # Defer import to avoid twilio dependency for users not making calls
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        if payload.use_twiml_bin and payload.twiml_bin_url:
            twiml_url = payload.twiml_bin_url
            twiml = None
        else:
            # Dynamic TwiML
            twiml = f'<Response><Connect><Stream url="{settings.WEBSOCKET_URL}/voice/{session_response.session_id}"/></Connect></Response>'
            twiml_url = None

        call_params = {
            "to": payload.to_number,
            "from_": payload.from_number,
        }
        if twiml_url:
            call_params["url"] = twiml_url
        else:
            call_params["twiml"] = twiml

        call = client.calls.create(**call_params)
        call_sid = call.sid
        call_placed = True
        message = "Call placed successfully"
    except Exception as e:
        logger.error("Failed to place Twilio call", error=str(e))
        message = str(e)

    return OutboundCallResponse(
        session_id=session_response.session_id,
        websocket_url=session_response.websocket_url,
        status=session_response.status,
        created_at=session_response.created_at,
        expires_at=session_response.expires_at,
        config_summary=session_response.config_summary,
        call_sid=call_sid,
        call_placed=call_placed,
        message=message
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """Get session details"""
    try:
        service = get_session_service()
        session = await service.get_session(session_id)
        
        return SessionDetailResponse(
            session_id=session.session_id,
            status=session.status.value,
            business=session.business_info,
            created_at=session.created_at.isoformat(),
            updated_at=session.updated_at.isoformat(),
            metadata=session.metadata,
            call_type=session.call_type
        )
    
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredException as e:
        raise HTTPException(status_code=410, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/config")
async def get_session_config(session_id: str):
    """Get Deepgram configuration for a session"""
    try:
        service = get_session_service()
        config = await service.get_session_config(session_id)
        return config
    
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredException as e:
        raise HTTPException(status_code=410, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving session config", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/complete")
async def get_complete_session(session_id: str):
    """
    Get complete session data (config + details) in one call.
    
    This endpoint is optimized for WebSocket server initialization to reduce latency.
    Instead of making two separate HTTP calls for config and details, this returns
    both in a single response, saving ~50-100ms per call setup.
    
    Returns:
        dict: {
            "config": Deepgram configuration dict,
            "details": Session details with metadata
        }
    """
    try:
        service = get_session_service()
        
        # Get both config and session details
        config = await service.get_session_config(session_id)
        session = await service.get_session(session_id)
        
        return {
            "config": config,
            "details": {
                "session_id": session.session_id,
                "status": session.status.value,
                "call_type": session.call_type.value if session.call_type else "inbound",
                "phone_number": session.metadata.get("phone_number", "unknown"),
                "business": session.business_info,
                "tenant_id": getattr(session, 'tenant_id', None),
                "organization_id": getattr(session, 'organization_id', None),
                "metadata": session.metadata,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }
        }
    
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredException as e:
        raise HTTPException(status_code=410, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving complete session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete/terminate a session"""
    try:
        service = get_session_service()
        deleted = await service.delete_session(session_id)
        
        if deleted:
            return {"message": "Session terminated", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    
    except Exception as e:
        logger.error("Error deleting session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status"),
    business_name: Optional[str] = Query(None, description="Filter by business name"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """List all sessions with optional filters"""
    try:
        service = get_session_service()
        sessions = await service.list_sessions(
            status=status,
            business_name=business_name,
            created_by=created_by,
            limit=limit,
            offset=offset
        )
        
        session_items = [
            SessionListItem(
                session_id=s.session_id,
                business=s.business_info.get("name", "Unknown"),
                status=s.status.value,
                created_at=s.created_at.isoformat(),
                call_type=s.call_type.value
            )
            for s in sessions
        ]
        
        return SessionListResponse(
            total=len(session_items),
            sessions=session_items
        )
    
    except Exception as e:
        logger.error("Error listing sessions", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
