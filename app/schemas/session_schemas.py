"""
Session Schemas
Request/Response models for session endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.schemas.config_schemas import VoiceAgentConfigSchema


class SessionCreateRequest(BaseModel):
    """Request to create a new voice agent session"""
    config: VoiceAgentConfigSchema
    phone_number: Optional[str] = Field(None, description="Phone number for outbound call")
    call_type: str = Field(default="inbound", description="inbound or outbound")


class SessionResponse(BaseModel):
    """Response after session creation"""
    session_id: str
    websocket_url: str
    status: str
    created_at: str
    expires_at: Optional[str] = None
    config_summary: Dict[str, Any]


class SessionDetailResponse(BaseModel):
    """Detailed session information"""
    session_id: str
    status: str
    business: Dict[str, Any]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    call_type: str


class SessionListItem(BaseModel):
    """Session list item"""
    session_id: str
    business: str
    status: str
    created_at: str
    call_type: str


class SessionListResponse(BaseModel):
    """List of sessions"""
    total: int
    sessions: list[SessionListItem]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    metrics: Dict[str, Any]
    services: Dict[str, str]
