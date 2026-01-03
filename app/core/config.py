"""
Application Configuration
Centralized configuration management using environment variables
"""

# Load .env early so Pydantic BaseSettings picks up values when instantiated.
try:
    from dotenv import load_dotenv
    # Load .env with override to ensure local .env values take precedence in development
    load_dotenv(override=True)
except Exception:
    # If python-dotenv is not available, BaseSettings will still read .env
    # using its own `env_file` mechanism, but loading here ensures IDE/run
    # environments that don't set the working directory still pick up values.
    pass

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Voice Agent API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    
    # API Server
    API_HOST: str = Field(default="0.0.0.0", description="API server binding host")
    API_PORT: int = Field(default=8000, description="API server port")
    API_RELOAD: bool = Field(default=True, description="Auto-reload on code changes")
    
    # API Client (for scripts connecting to API)
    API_CLIENT_HOST: str = Field(default="localhost", description="API client connection host")
    
    # WebSocket Server
    WEBSOCKET_HOST: str = Field(default="localhost", description="WebSocket server host")
    WEBSOCKET_PORT: int = Field(default=5000, description="WebSocket server port")
    BASE_WEBSOCKET_URL: str = Field(default="ws://localhost:5000", description="Base WebSocket URL")
    
    # ngrok URLs (optional - for development)
    NGROK_URL: Optional[str] = Field(default=None, description="ngrok HTTP URL (optional)")
    WEBSOCKET_URL: Optional[str] = Field(default=None, description="ngrok WebSocket URL (optional)")
    
    # External Services
    DEEPGRAM_API_KEY: str = Field(..., description="Deepgram API key (required)")
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, description="Twilio account SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, description="Twilio auth token")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, description="Twilio phone number")
    
    # Convex DB
    CONVEX_URL: str = Field(..., description="Convex Deployment URL")
    CONVEX_DEPLOY_KEY: Optional[str] = Field(default=None, description="Convex Deploy Key (for admin)")
    
    # CORS
    CORS_ORIGINS: list = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    # Deepgram speak model (default to Thalia)
    DEEPGRAM_SPEAK_MODEL: str = Field(default="aura-2-thalia-en", description="Deepgram TTS model to use for Speak API")
    
    # Session Management
    SESSION_TTL_SECONDS: int = Field(default=3600, description="Session time-to-live in seconds")
    MAX_SESSIONS_PER_USER: int = Field(default=10, description="Maximum sessions per user")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Using lru_cache ensures settings are loaded only once
    """
    return Settings()


# Export for easy access
settings = get_settings()
