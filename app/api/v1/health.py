"""
Health & System Routes
API endpoints for health checks and system information
"""

from fastapi import APIRouter
from datetime import datetime
import os

from app.schemas.session_schemas import HealthResponse
from app.services.session_service import get_session_service
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["system"])


@router.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "documentation": "/docs"
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Detailed health check endpoint
    Returns service status, metrics, and external service configuration
    """
    service = get_session_service()
    active_sessions = await service.count_sessions()
    
    # Database is ConvexDB (serverless)
    db_type = "convexdb"
    convex_configured = bool(settings.CONVEX_URL)
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        metrics={
            "active_sessions": active_sessions,
            "websocket_connections": 0,
        },
        services={
            "deepgram_key": "configured" if settings.DEEPGRAM_API_KEY else "missing",
            "twilio": "configured" if settings.TWILIO_ACCOUNT_SID else "not configured",
            "database": db_type,
            "convex": "configured" if convex_configured else "missing"
        }
    )


@router.get("/info")
async def system_info():
    """Get system information"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "api_host": settings.API_HOST,
        "api_port": settings.API_PORT,
        "websocket_host": settings.WEBSOCKET_HOST,
        "websocket_port": settings.WEBSOCKET_PORT
    }
