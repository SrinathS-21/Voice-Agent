"""
Configuration Schemas
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any


class AudioConfigSchema(BaseModel):
    """Audio configuration schema"""
    input_encoding: str = Field(default="mulaw", description="Audio input encoding")
    input_sample_rate: int = Field(default=8000, description="Audio input sample rate")
    output_encoding: str = Field(default="mulaw", description="Audio output encoding")
    output_sample_rate: int = Field(default=8000, description="Audio output sample rate")
    output_container: str = Field(default="none", description="Audio output container")


class ListenProviderSchema(BaseModel):
    """Speech-to-Text provider configuration"""
    type: str = Field(default="deepgram", description="STT provider type")
    model: str = Field(default="nova-3", description="STT model")
    keyterms: Optional[List[str]] = Field(default=None, description="Keywords for better recognition")


class ThinkProviderSchema(BaseModel):
    """LLM provider configuration"""
    type: str = Field(default="open_ai", description="LLM provider type")
    model: str = Field(default="gpt-4o-mini", description="LLM model")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")


class SpeakProviderSchema(BaseModel):
    """Text-to-Speech provider configuration"""
    type: str = Field(default="deepgram", description="TTS provider type")
    model: str = Field(default="aura-2-thalia-en", description="TTS voice model")


class FunctionDefinitionSchema(BaseModel):
    """Function definition schema"""
    name: str = Field(..., description="Function name")
    description: str = Field(..., description="Function description")
    parameters: Dict[str, Any] = Field(..., description="Function parameters (JSON Schema)")


class BusinessInfoSchema(BaseModel):
    """Business information schema"""
    name: str = Field(..., description="Business name", min_length=1)
    type: str = Field(..., description="Business type (restaurant, pharmacy, etc.)")
    description: Optional[str] = Field(None, description="Business description")
    specialties: Optional[List[str]] = Field(None, description="Business specialties")


class VoiceAgentConfigSchema(BaseModel):
    """Complete voice agent configuration schema"""
    
    # Business Information
    business: BusinessInfoSchema
    
    # Agent Configuration
    language: str = Field(default="en", description="Agent language")
    system_prompt: str = Field(..., description="Custom system prompt for the agent", min_length=50)
    greeting: str = Field(..., description="Initial greeting message", min_length=10)
    
    # Functions available to agent
    functions: List[FunctionDefinitionSchema] = Field(..., description="Available functions", min_items=1)
    
    # Provider Configuration (optional, uses defaults if not provided)
    audio: Optional[AudioConfigSchema] = None
    listen_provider: Optional[ListenProviderSchema] = None
    think_provider: Optional[ThinkProviderSchema] = None
    speak_provider: Optional[SpeakProviderSchema] = None
    
    # Metadata
    created_by: Optional[str] = Field(None, description="User/tenant ID")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    
    @validator('system_prompt')
    def validate_prompt(cls, v):
        if len(v) < 50:
            raise ValueError('System prompt must be at least 50 characters')
        return v
    
    @validator('functions')
    def validate_functions(cls, v):
        if not v:
            raise ValueError('At least one function is required')
        return v
