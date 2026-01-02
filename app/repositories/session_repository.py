"""
Session Repository
Data access layer for session management
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.models.session import Session, SessionStatus
from app.core.exceptions import SessionNotFoundException
from app.core.logging import get_logger

logger = get_logger(__name__)


class SessionRepository:
    """
    Repository for session data access
    Uses in-memory storage for hot sessions, with ConvexDB for persistence
    """
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
    
    async def create(self, session: Session) -> Session:
        """Create a new session"""
        self._sessions[session.session_id] = session
        logger.info(
            "Session created",
            session_id=session.session_id,
            business=session.business_info.get("name")
        )
        return session
    
    async def get(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("Session not found", session_id=session_id)
            return None
        return session
    
    async def get_or_fail(self, session_id: str) -> Session:
        """Get session or raise exception"""
        session = await self.get(session_id)
        if not session:
            raise SessionNotFoundException(session_id)
        return session
    
    async def update(self, session: Session) -> Session:
        """Update session"""
        session.updated_at = datetime.utcnow()
        self._sessions[session.session_id] = session
        logger.info("Session updated", session_id=session.session_id)
        return session
    
    async def delete(self, session_id: str) -> bool:
        """Delete session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session deleted", session_id=session_id)
            return True
        return False
    
    async def list(
        self,
        status: Optional[str] = None,
        business_name: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """List sessions with filters"""
        sessions = list(self._sessions.values())
        
        # Apply filters
        if status:
            sessions = [s for s in sessions if s.status.value == status]
        if business_name:
            sessions = [s for s in sessions if s.business_info.get("name") == business_name]
        if created_by:
            sessions = [s for s in sessions if s.created_by == created_by]
        
        # Apply pagination
        return sessions[offset:offset + limit]
    
    async def count(self) -> int:
        """Count total sessions"""
        return len(self._sessions)
    
    async def cleanup_expired(self) -> int:
        """Remove expired sessions"""
        expired_sessions = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired()
        ]
        
        for session_id in expired_sessions:
            await self.delete(session_id)
        
        if expired_sessions:
            logger.info("Cleaned up expired sessions", count=len(expired_sessions))
        
        return len(expired_sessions)


# Singleton instance
_session_repository: Optional[SessionRepository] = None


def get_session_repository() -> SessionRepository:
    """Get session repository instance"""
    global _session_repository
    if _session_repository is None:
        _session_repository = SessionRepository()
    return _session_repository
