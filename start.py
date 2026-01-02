"""
Simple startup script for MVP
Runs database initialization and starts the API server
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
import uvicorn

setup_logging()
logger = get_logger(__name__)


async def initialize():
    """Initialize application"""
    logger.info("🔧 Initializing application...")
    # Convex initialization is handled via deployment
    logger.info("✅ Application initialized")


def main():
    """Main startup function"""
    print("\n" + "="*50)
    print("🚀 Voice Agent MVP - Starting...")
    print("="*50 + "\n")
    
    # Initialize application
    asyncio.run(initialize())
    
    print("\n" + "="*50)
    print("✅ Ready! Starting API Server...")
    print(f"📍 API: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📖 Docs: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print(f"📊 Analytics: http://{settings.API_HOST}:{settings.API_PORT}/api/v1/analytics")
    print("="*50 + "\n")
    
    # Start server
    uvicorn.run(
        "server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level="info"
    )


if __name__ == "__main__":
    main()
