from fastapi import APIRouter, HTTPException, Depends
from app.core.logging import get_logger
from app.core.convex_client import get_convex_client
import json

logger = get_logger(__name__)
router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{session_id}", name="Get Artifacts")
async def get_artifacts(session_id: str):
    """
    Retrieve artifacts (transcripts, logs, recordings) for a session.
    It looks up the session in Convex and returns relevant data.
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
    
    # Extract artifacts if available (e.g. from config)
    # The previous code assumed config['artifacts'].
    artifacts = config_data.get("artifacts") or []
    
    # Also include transcript if available, as some might consider it an artifact?
    # The query param was just "artifacts".
    
    return {"session_id": session_id, "artifacts": artifacts}
