"""
Custom Exceptions
Application-specific exception classes
"""

from typing import Any, Optional


class VoiceAgentException(Exception):
    """Base exception for all voice agent errors"""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class SessionNotFoundException(VoiceAgentException):
    """Raised when a session is not found"""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            code="SESSION_NOT_FOUND",
            details={"session_id": session_id}
        )


class SessionExpiredException(VoiceAgentException):
    """Raised when a session has expired"""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session expired: {session_id}",
            code="SESSION_EXPIRED",
            details={"session_id": session_id}
        )


class ConfigurationException(VoiceAgentException):
    """Raised when configuration is invalid"""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details=details
        )


class FunctionExecutionException(VoiceAgentException):
    """Raised when a function execution fails"""
    
    def __init__(self, function_name: str, error: str):
        super().__init__(
            message=f"Function execution failed: {function_name}",
            code="FUNCTION_EXECUTION_ERROR",
            details={"function_name": function_name, "error": error}
        )


class ExternalServiceException(VoiceAgentException):
    """Raised when an external service (Deepgram, Twilio) fails"""
    
    def __init__(self, service: str, error: str):
        super().__init__(
            message=f"External service error: {service}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "error": error}
        )


class ValidationException(VoiceAgentException):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {}
        )


class RateLimitException(VoiceAgentException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, limit: int, window: str):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            code="RATE_LIMIT_EXCEEDED",
            details={"limit": limit, "window": window}
        )
