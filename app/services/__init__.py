"""
Service Layer
Business logic and data processing services.
Domain-agnostic - works with any business type.

Simplified architecture:
- Document parsing → Paragraph chunking → RAG storage → Semantic search
- No LLM extraction, no filters, no content type detection
"""

from app.services.chunking_service import ChunkingService, ChunkingStrategy, get_chunking_service
from app.services.knowledge_base_service import KnowledgeBaseService, get_knowledge_base_service
from app.services.document_parser_service import DocumentParserService, get_document_parser
from app.services.knowledge_ingestion_service import KnowledgeIngestionService, get_ingestion_service
from app.services.function_generator_service import FunctionGeneratorService, get_function_generator_service
from app.services.prompt_builder_service import PromptBuilderService, get_prompt_builder_service
from app.services.voice_knowledge_service import VoiceKnowledgeService, get_voice_knowledge_service, clear_service_cache

__all__ = [
    # Chunking
    "ChunkingService", 
    "ChunkingStrategy",
    "get_chunking_service",
    # Knowledge Base
    "KnowledgeBaseService",
    "get_knowledge_base_service",
    # Document Parsing
    "DocumentParserService",
    "get_document_parser",
    # Ingestion (simplified)
    "KnowledgeIngestionService",
    "get_ingestion_service",
    # Function Generation
    "FunctionGeneratorService",
    "get_function_generator_service",
    # Prompt Building
    "PromptBuilderService",
    "get_prompt_builder_service",
    # Voice Knowledge (optimized)
    "VoiceKnowledgeService",
    "get_voice_knowledge_service",
    "clear_service_cache",
]
