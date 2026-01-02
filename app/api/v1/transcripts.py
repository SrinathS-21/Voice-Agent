from fastapi import APIRouter, HTTPException, Query, Response
from app.core.convex_client import get_convex_client
import json

router = APIRouter(prefix="/transcripts", tags=["transcripts"])

@router.get("/{session_id}/download")
async def download_transcript(session_id: str):
    """Download the transcript JSON for a session as an attachment
    """
    client = get_convex_client()
    sess = await client.query("callSessions:getBySessionId", {"sessionId": session_id})
    
    if not sess:
         # Fallback logic not really possible without index in Convex unless we scan
         # But assuming migration worked, session should be there.
         raise HTTPException(status_code=404, detail="Session not found")
         
    content = {}
    if sess.get("config"):
        try:
             content = json.loads(sess.get("config"))
        except:
             pass
             
    # Normalize: prefer `conversation` key if present
    # But usually this endpoint returns the whole config dump as JSON
    
    body = json.dumps(content, indent=2)
    headers = {"Content-Disposition": f"attachment; filename=transcript_{session_id}.json"}
    return Response(content=body, media_type="application/json", headers=headers)
