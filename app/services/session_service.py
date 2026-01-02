"""
Session Service
Business logic for session management
"""

from datetime import datetime, timedelta
from typing import Optional, List

from app.models.session import Session, SessionStatus, CallType
from app.repositories.session_repository import SessionRepository, get_session_repository
from app.services.config_service import ConfigService
from app.schemas.config_schemas import VoiceAgentConfigSchema
from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import SessionNotFoundException, SessionExpiredException
from app.core.convex_client import get_convex_client
import json

logger = get_logger(__name__)


class SessionService:
    """Service for session management operations"""
    
    def __init__(self, repository: Optional[SessionRepository] = None):
        self.repository = repository or get_session_repository()
        self.config_service = ConfigService()
    
    async def create_session(
        self,
        config: VoiceAgentConfigSchema,
        call_type: CallType = CallType.INBOUND,
        phone_number: Optional[str] = None,
        tenant_id: Optional[int] = None,
        organization_id: Optional[str] = None
    ) -> Session:
        """
        Create a new voice agent session
        
        Args:
            config: Voice agent configuration
            call_type: Type of call (inbound/outbound)
            phone_number: Phone number for outbound calls
            
        Returns:
            Created session
        """
        # Generate Deepgram configuration
        deepgram_config = self.config_service.generate_deepgram_config(config)

        # If a phone number is provided, check for a bound agent and merge agent config
        agent_meta = None
        # If a phone number is provided, check for a bound agent and merge agent config
        agent_meta = None
        try:
            if phone_number:
                client = get_convex_client()
                # Query phone config from Convex
                p = await client.query("phoneConfigs:getByPhoneNumber", {"phoneNumber": phone_number})
                
                if p and p.get("agentId"):
                    # Get agent details (assuming we have a query or can fetch from `agents` table)
                    # We need a query for getting agent by ID. 
                    # Assuming "agents:get" or similar. If not, we can query by ID if we exposed it.
                    # Or since agentId is an ID, we might need a generic get or getBy keys.
                    # Let's try to query agents directly if possible or add a query.
                    # For MVP, let's assume we can skip complex agent merging or implement a basic lookup later
                    # if the Convex migration script populated agents.
                    pass
                    # Implementation TODO: Fetch agent from Convex and merge config similar to SQL version.
                    # For now, we rely on the phoneConfig having the configJson which is main path.
                    
        except Exception:
            logger.error("Failed to merge agent config based on phone number", exc_info=True)
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(seconds=settings.SESSION_TTL_SECONDS)
        
        # Create session
        session = Session(
            config=deepgram_config,
            business_info=config.business.dict(),
            tenant_id=tenant_id,
            organization_id=organization_id,
            call_type=call_type,
            status=SessionStatus.ACTIVE,
            created_by=config.created_by,
            tags=config.tags or [],
            metadata={
                "functions_count": len(config.functions),
                "language": config.language,
                "business_name": config.business.name,
                "phone_number": phone_number
            },
            expires_at=expires_at
        )
        
        # Save to repository
        await self.repository.create(session)

        # If we found agent metadata earlier, attach it to the persisted session and update
        if agent_meta:
            session.metadata = session.metadata or {}
            session.metadata.update(agent_meta)
            try:
                await self.repository.update(session)
            except Exception:
                logger.error("Failed to persist session agent metadata", exc_info=True)
        
        logger.info(
            "Session created successfully",
            session_id=session.session_id,
            business=config.business.name,
            call_type=call_type.value
        )
        
        return session
    
    async def get_session(self, session_id: str) -> Session:
        """
        Get session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Session
            
        Raises:
            SessionNotFoundException: If session not found
            SessionExpiredException: If session has expired
        """
        session = await self.repository.get_or_fail(session_id)
        
        if session.is_expired():
            logger.warning("Attempted to access expired session", session_id=session_id)
            raise SessionExpiredException(session_id)
        
        return session
    
    async def get_session_config(self, session_id: str) -> dict:
        """Get Deepgram configuration for a session"""
        session = await self.get_session(session_id)
        return session.config
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete/terminate a session"""
        session = await self.repository.get(session_id)
        if session:
            session.update_status(SessionStatus.ENDED)
            await self.repository.update(session)
            await self.repository.delete(session_id)
            
            logger.info("Session terminated", session_id=session_id)
            return True
        return False
    
    async def list_sessions(
        self,
        status: Optional[str] = None,
        business_name: Optional[str] = None,
        created_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """List sessions with filters"""
        return await self.repository.list(
            status=status,
            business_name=business_name,
            created_by=created_by,
            limit=limit,
            offset=offset
        )
    
    async def count_sessions(self) -> int:
        """Count total sessions"""
        return await self.repository.count()
    
    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        return await self.repository.cleanup_expired()


def get_session_service() -> SessionService:
    """Get session service instance"""
    # Use Convex repository implementation
    # We no longer check settings.PERSIST_SESSIONS for DB type, 
    # but we can respect it for whether to save at all? 
    # Current codebase assumes persistence if Convex is enabled.
    from app.repositories.convex_session_repository import ConvexSessionRepository
    return SessionService(repository=ConvexSessionRepository())
