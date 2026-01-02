"""
Logging Configuration
Centralized logging setup with structured logging support
"""

import logging
import sys
from typing import Any, Dict
from datetime import datetime
import json

from app.core.config import settings


class StructuredLogger:
    """Structured logger that outputs JSON for production"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal log method with structured output"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "logger": self.logger.name,
            "message": message,
            **kwargs
        }
        
        if settings.ENVIRONMENT == "production":
            # JSON output for production
            self.logger.log(
                getattr(logging, level),
                json.dumps(log_data)
            )
        else:
            # Human-readable for development
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            log_msg = f"{message} | {extra_info}" if extra_info else message
            self.logger.log(getattr(logging, level), log_msg)
    
    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log("CRITICAL", message, **kwargs)


def setup_logging():
    """Configure application-wide logging"""
    
    # Root logger configuration
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=settings.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Disable noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("deepgram").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)
