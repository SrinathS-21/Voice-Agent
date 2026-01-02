"""
Session Data Models
Domain models for session management
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class SessionStatus(str, Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"
    ERROR = "error"


class CallType(str, Enum):
    """Call type enumeration"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Session:
    """Session domain model"""
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        config: Optional[Dict] = None,
        business_info: Optional[Dict] = None,
        call_type: CallType = CallType.INBOUND,
        status: SessionStatus = SessionStatus.ACTIVE,
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[int] = None,
        organization_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.config = config or {}
        self.business_info = business_info or {}
        self.tenant_id = tenant_id if tenant_id is not None else (self.business_info.get("tenant_id") if isinstance(self.business_info, dict) else None)
        self.organization_id = organization_id if organization_id is not None else (self.business_info.get("organization_id") if isinstance(self.business_info, dict) else None)
        self.call_type = call_type
        self.status = status
        self.created_by = created_by
        self.tags = tags or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.expires_at = expires_at
    
    def to_dict(self) -> Dict:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "config": self.config,
            "business_info": self.business_info,
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "call_type": self.call_type.value,
            "status": self.status.value,
            "created_by": self.created_by,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Session":
        """Create session from dictionary"""
        return cls(
            session_id=data.get("session_id"),
            config=data.get("config"),
            business_info=data.get("business_info"),
            call_type=CallType(data.get("call_type", "inbound")),
            status=SessionStatus(data.get("status", "active")),
            created_by=data.get("created_by"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            tenant_id=data.get("tenant_id"),
            organization_id=data.get("organization_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def update_status(self, status: SessionStatus):
        """Update session status"""
        self.status = status
        self.updated_at = datetime.utcnow()
