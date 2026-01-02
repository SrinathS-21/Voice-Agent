"""
Configuration Service
Handles Deepgram configuration generation
"""

from typing import Dict
from app.schemas.config_schemas import (
    VoiceAgentConfigSchema,
    AudioConfigSchema,
    ListenProviderSchema,
    ThinkProviderSchema,
    SpeakProviderSchema
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConfigService:
    """Service for generating Deepgram-compatible configurations"""
    
    @staticmethod
    def generate_deepgram_config(config: VoiceAgentConfigSchema) -> Dict:
        """
        Generate Deepgram-compatible configuration from voice agent config
        
        Args:
            config: Voice agent configuration schema
            
        Returns:
            Deepgram configuration dictionary
        """
        # Use provided or default configurations
        audio_config = config.audio or AudioConfigSchema()
        listen_provider = config.listen_provider or ListenProviderSchema()
        think_provider = config.think_provider or ThinkProviderSchema()
        speak_provider = config.speak_provider or SpeakProviderSchema()
        
        deepgram_config = {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": audio_config.input_encoding,
                    "sample_rate": audio_config.input_sample_rate
                },
                "output": {
                    "encoding": audio_config.output_encoding,
                    "sample_rate": audio_config.output_sample_rate,
                    "container": audio_config.output_container
                }
            },
            "agent": {
                "language": config.language,
                "listen": {
                    "provider": {
                        "type": listen_provider.type,
                        "model": listen_provider.model,
                    }
                },
                "think": {
                    "provider": {
                        "type": think_provider.type,
                        "model": think_provider.model,
                        "temperature": think_provider.temperature
                    },
                    "prompt": config.system_prompt,
                    "functions": [func.dict() for func in config.functions]
                },
                "speak": {
                    "provider": {
                        "type": speak_provider.type,
                        "model": speak_provider.model
                    }
                },
                "greeting": config.greeting
            }
        }
        
        # Add keyterms if provided
        if listen_provider.keyterms:
            deepgram_config["agent"]["listen"]["provider"]["keyterms"] = listen_provider.keyterms
        
        logger.debug(
            "Generated Deepgram config",
            business=config.business.name,
            functions_count=len(config.functions)
        )
        
        return deepgram_config
