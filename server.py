"""
Main FastAPI Application
Clean, production-ready API server with proper structure
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import VoiceAgentException
from app.api.v1 import sessions, health, templates, analytics, phone_configs, twilio_webhooks, tenants, admin
from app.api.v1 import calls, artifacts, assistant, transcripts
from app.api.v1 import vapi_compat
from app.api.v1 import knowledge_base
from app.api.v1 import domains
from app.services.session_service import get_session_service
from app.api.v1 import agents

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management
    Startup and shutdown events
    """
    # Startup
    logger.info(
        "Starting Voice Agent API",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT
    )
    
    # Start background tasks
    cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    
    yield
    
    # Shutdown
    logger.info("Shutting down Voice Agent API")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Dynamic Voice Agent API - Create custom AI voice assistants",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(VoiceAgentException)
async def voice_agent_exception_handler(request: Request, exc: VoiceAgentException):
    """Handle custom voice agent exceptions"""
    logger.error(
        "Voice agent exception",
        code=exc.code,
        message=exc.message,
        details=exc.details
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {} if settings.ENVIRONMENT == "production" else {"error": str(exc)}
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(phone_configs.router, prefix="/api/v1")
app.include_router(twilio_webhooks.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

app.include_router(calls.router, prefix="/api/v1")
app.include_router(artifacts.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(transcripts.router, prefix="/api/v1")
app.include_router(vapi_compat.router)
app.include_router(__import__('app.api.v1.clover_tools', fromlist=['router']).router)
app.include_router(agents.router, prefix="/api/v1")
app.include_router(knowledge_base.router, prefix="/api/v1")
app.include_router(domains.router, prefix="/api/v1")


# Background Tasks
async def cleanup_expired_sessions():
    """Background task to clean up expired sessions"""
    service = get_session_service()
    
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            cleaned = await service.cleanup_expired_sessions()
            if cleaned > 0:
                logger.info("Cleaned up expired sessions", count=cleaned)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in cleanup task", error=str(e))


# Development server
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )
