"""
Convex Session Repository
Data access layer for session management using Convex DB
"""

from typing import List, Optional
from datetime import datetime
import json
from app.models.session import Session, SessionStatus, CallType
from app.core.convex_client import get_convex_client, ConvexClient
from app.core.logging import get_logger
from app.core.exceptions import SessionNotFoundException

logger = get_logger(__name__)


class ConvexSessionRepository:
    """
    Repository for session data access using Convex DB
    """
    
    def __init__(self, client: Optional[ConvexClient] = None):
        self.client = client or get_convex_client()
        self._external_client = client is not None # Track if client was passed in (don't close if not own)

    async def create(self, session: Session) -> Session:
        """
        Create a new session in Convex
        """
        try:
            # We use the generic 'create' or 'createImported' if specific ID needed?
            # 'create' in convex/callSessions.ts takes sessionId.
            
            # Prepare config JSON
            config_str = json.dumps(session.config) if session.config else None
            
            await self.client.mutation("callSessions:create", {
                "sessionId": session.session_id,
                "organizationId": getattr(session, 'organization_id', 'default'), # Default for now
                "phoneNumber": session.metadata.get("phone_number", "unknown"),
                "callType": session.call_type.value if session.call_type else "inbound",
                "agentType": session.business_info.get("type", "unknown") if session.business_info else "unknown",
                "config": config_str
            })
            
            logger.info(
                "Session created in Convex",
                session_id=session.session_id,
                business=session.business_info.get("name")
            )
            return session
        except Exception as e:
            logger.error(f"Failed to create session in Convex: {e}")
            raise

    async def get(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID from Convex
        """
        try:
            data = await self.client.query("callSessions:getBySessionId", {"sessionId": session_id})
            
            if not data:
                return None
                
            # Convert Convex data to Session model
            return self._map_convex_to_session(data)
        except Exception as e:
            logger.error(f"Failed to get session from Convex: {e}")
            return None

    async def get_or_fail(self, session_id: str) -> Session:
        """Get session or raise exception"""
        session = await self.get(session_id)
        if not session:
            raise SessionNotFoundException(session_id)
        return session

    async def update(self, session: Session) -> Session:
        """
        Update session in Convex (status, etc.)
        Note: The Session object changes might need to be proactively synced.
        Specific mutations exist for Status and CallSid.
        For general update, we might need a general update mutation or just update specific fields.
        """
        try:
            # Update status
            ended_at_ms = int(session.expires_at.timestamp() * 1000) if session.expires_at else None
            # Note: expires_at roughly maps to ended_at in our logic for 'completed' sessions? 
            # Or is it TTL? 
            # In session_service, delete_session sets status=ENDED.
            # Let's map status.
            
            await self.client.mutation("callSessions:updateStatus", {
                "sessionId": session.session_id,
                "status": session.status.value,
                "endedAt": ended_at_ms,
                "durationSeconds": session.duration_seconds
            })
            
            # If call_sid changed?
            # We assume session object is up to date.
            
            return session
        except Exception as e:
            logger.error(f"Failed to update session in Convex: {e}")
            raise

    async def delete(self, session_id: str) -> bool:
        """
        Delete session (soft delete or set status to expired?)
        repo.delete in service calls update(status=ENDED) then delete.
        We can just rely on update status=ENDED/EXPIRED.
        If actual delete is needed, we need a delete mutation.
        For now, let's treat delete as 'ensure it is gone or marked inactive'.
        Service calls delete() after update().
        """
        # We don't have a hard delete mutation in schema yet.
        # Let's assume update status is sufficient for now, or add delete mutation later.
        # Returning True to satisfy interface.
        return True

    async def list(
        self,
        status: Optional[str] = None,
        business_name: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """List sessions with filters"""
        try:
            # We have getRecentSessions(organizationId) and getActiveCalls
            # For comprehensive search, we might need a generic list query.
            # For MVP, we'll implement organization-based listing (default org).
            
            org_id = "default"
            if status == "active":
                raw_sessions = await self.client.query("callSessions:getActiveCalls", {"organizationId": org_id})
            else:
                 raw_sessions = await self.client.query("callSessions:getRecentSessions", {
                     "organizationId": org_id,
                     "limit": limit
                 })
            
            # Filter in memory if needed (offset, other filters)
            # Convex query returns list.
            
            sessions = []
            for s in raw_sessions:
                sessions.append(self._map_convex_to_session(s))
            
            # Offset slicing
            return sessions[offset:offset+limit]
            
        except Exception as e:
            logger.error(f"Failed to list sessions from Convex: {e}")
            return []

    async def count(self) -> int:
        """Count total sessions"""
        # Requires a count query or scanning.
        # MVP: Return 0 or Implement count query.
        return 0

    async def cleanup_expired(self) -> int:
        """Remove expired sessions"""
        # Logic should be in a Convex cron or scheduled function.
        # Client side cleanup is inefficient.
        return 0
    
    def _map_convex_to_session(self, data: dict) -> Session:
        """Map Convex dictionary to Session model"""
        
        # Parse config json
        config = {}
        if data.get("config"):
            try:
                config = json.loads(data["config"])
            except:
                pass
                
        # Times
        created_at = datetime.fromtimestamp(data["createdAt"] / 1000) if data.get("createdAt") else datetime.utcnow()
        ended_at = datetime.fromtimestamp(data["endedAt"] / 1000) if data.get("endedAt") else None
        
        return Session.from_dict({
            'session_id': data["sessionId"],
            'config': config,
            'business_info': {'name': data.get("agentType", "unknown")}, # Mapping agentType to name for now
            'call_type': data.get("callType"),
            'status': data.get("status"),
            'tenant_id': None, 
            'organization_id': data.get("organizationId"),
            'metadata': {'phone_number': data.get("phoneNumber")},
            'created_at': created_at.isoformat(),
            'updated_at': created_at.isoformat(), # approximate
            'expires_at': ended_at.isoformat() if ended_at else None,
            'duration_seconds': data.get("durationSeconds")
        })

    def __del__(self):
        # Async cleanup is hard in __del__
        pass
