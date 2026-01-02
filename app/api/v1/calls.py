from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import Optional
from app.services.session_service import SessionService
from app.core.logging import get_logger
from app.core.convex_client import get_convex_client

logger = get_logger(__name__)
router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/", name="List calls")
async def list_calls(tenant_id: Optional[str] = None, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """List recent call sessions"""
    client = get_convex_client()
    # If tenant_id is provided (as string ID or slug), filter by it.
    if tenant_id:
        # Check if slug or ID. Naive: if no spaces and short, assume ID? 
        # Better: try to resolve slug if it's not ID format? 
        # For now, let's assume filtering by organizationId directly if passed.
        # Actually, let's support passing slug by looking it up.
        
        # Try looking up as organization slug first
        org = await client.query("organizations:getBySlug", {"slug": tenant_id})
        target_org_id = org["_id"] if org else tenant_id
        
        sessions = await client.query("callSessions:listByOrganization", {"organizationId": str(target_org_id)})
        # Pagination manual for now (Convex 'take' used in query, but offset manual slice)
        total = len(sessions)
        paginated = sessions[offset:offset+limit]
    else:
        # Warning: listing ALL calls might be heavy. We added getAllActiveCalls but not getAllRecent.
        # Let's fallback to empty or implement getAllRecent if needed.
        # For now, require tenant_id or return empty to be safe, or just active ones?
        # Let's return empty if no tenant to avoid scanning specific tables without index.
        return {"total": 0, "items": []}

    return {
        "total": total,
        "items": [
            {
                "session_id": s.get("sessionId"),
                "call_sid": s.get("callSid"),
                "phone_number": s.get("phoneNumber"),
                "agent_type": s.get("agentType"),
                "status": s.get("status"),
                "started_at": s.get("startedAt"), # epoch time, client can format
                "ended_at": s.get("endedAt"),
                "duration_seconds": s.get("durationSeconds"),
            }
            for s in paginated
        ]
    }


@router.get("/{session_id}")
async def get_call(session_id: str):
    """Get call session details"""
    client = get_convex_client()
    sess = await client.query("callSessions:getBySessionId", {"sessionId": session_id})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "session_id": sess.get("sessionId"),
        "call_sid": sess.get("callSid"),
        "phone_number": sess.get("phoneNumber"),
        "agent_type": sess.get("agentType"),
        "status": sess.get("status"),
        "started_at": sess.get("startedAt"),
        "ended_at": sess.get("endedAt"),
        "duration_seconds": sess.get("durationSeconds"),
        "config": sess.get("config"),
    }


@router.get("/{session_id}/transcript")
async def get_transcript(session_id: str):
    """Return transcript / conversation JSON stored in session.config
    """
    client = get_convex_client()
    sess = await client.query("callSessions:getBySessionId", {"sessionId": session_id})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    
    import json
    config_data = {}
    if sess.get("config"):
        try:
             config_data = json.loads(sess.get("config"))
        except:
             pass
             
    # Normalize: prefer `conversation` key if present
    conv = config_data.get("conversation") or config_data
    return {"session_id": session_id, "transcript": conv}


# Old SQL endpoints removed
