"""
Prompt Builder Service
Assembles contextual system prompts for voice agents.
Combines domain templates, knowledge base context, and conversation history.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.core.convex_client import get_convex_client
from app.domains.registry import DomainRegistry, DomainConfig

logger = get_logger(__name__)


class PromptBuilderService:
    """
    Service for building contextual system prompts.
    Assembles prompts from:
    - Domain templates
    - Knowledge base context (from semantic search)
    - Conversation history
    - Function definitions
    - Business-specific configuration
    """
    
    def __init__(self):
        self.convex = get_convex_client()
        self.registry = DomainRegistry()
        
        # Configuration
        self.max_context_chunks = 5
        self.max_history_turns = 5
        self.max_context_tokens = 2000  # Approximate limit for context
    
    async def build_system_prompt(
        self,
        organization_id: str,
        domain_type: str,
        business_name: str,
        agent_name: str = "Assistant",
        query: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        include_knowledge_context: bool = True,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        Build a complete system prompt for the voice agent.
        
        Args:
            organization_id: Organization ID
            domain_type: Business domain type
            business_name: Name of the business
            agent_name: Name for the agent
            query: Current user query (for knowledge retrieval)
            conversation_history: Recent conversation turns
            include_knowledge_context: Whether to include KB context
            custom_instructions: Additional custom instructions
            
        Returns:
            Complete system prompt string
        """
        # Get domain configuration
        domain = self.registry.get_domain(domain_type)
        if not domain:
            logger.warning(
                "Unknown domain, using generic prompt",
                domain_type=domain_type
            )
            domain = self._get_generic_domain()
        
        # Build prompt sections
        sections = []
        
        # 1. Role and Identity
        role_section = domain.system_prompt_template.format(
            business_name=business_name,
            agent_name=agent_name
        )
        sections.append(role_section)
        
        # 2. Knowledge Context (if enabled and query provided)
        if include_knowledge_context and query:
            knowledge_context = await self._get_knowledge_context(
                organization_id=organization_id,
                query=query,
                domain_type=domain_type
            )
            if knowledge_context:
                sections.append(self._format_knowledge_section(knowledge_context))
        
        # 3. Conversation History
        if conversation_history:
            history_section = self._format_history_section(conversation_history)
            if history_section:
                sections.append(history_section)
        
        # 4. Disclaimers (if any for domain)
        if domain.disclaimers:
            disclaimers = "\n".join(f"- {d}" for d in domain.disclaimers)
            sections.append(f"\nIMPORTANT DISCLAIMERS:\n{disclaimers}")
        
        # 5. Custom Instructions
        if custom_instructions:
            sections.append(f"\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}")
        
        # Assemble final prompt
        prompt = "\n\n".join(sections)
        
        logger.debug(
            "Built system prompt",
            organization_id=organization_id,
            domain=domain_type,
            prompt_length=len(prompt),
            has_knowledge_context=include_knowledge_context and bool(query)
        )
        
        return prompt
    
    async def build_query_enhanced_prompt(
        self,
        base_prompt: str,
        organization_id: str,
        query: str,
        source_type: Optional[str] = None
    ) -> str:
        """
        Enhance an existing prompt with relevant knowledge context.
        Used during conversation to inject relevant information.
        
        Args:
            base_prompt: Existing system prompt
            organization_id: Organization ID
            query: Current user query
            source_type: Optional filter for knowledge type
            
        Returns:
            Enhanced prompt with knowledge context
        """
        knowledge_context = await self._get_knowledge_context(
            organization_id=organization_id,
            query=query,
            source_type=source_type
        )
        
        if not knowledge_context:
            return base_prompt
        
        # Insert knowledge context before the guidelines section
        knowledge_section = self._format_knowledge_section(knowledge_context)
        
        # Try to insert before GUIDELINES or IMPORTANT section
        insert_markers = ["IMPORTANT GUIDELINES:", "GUIDELINES:", "CRITICAL GUIDELINES:"]
        
        for marker in insert_markers:
            if marker in base_prompt:
                parts = base_prompt.split(marker, 1)
                return f"{parts[0]}{knowledge_section}\n\n{marker}{parts[1]}"
        
        # If no marker found, append at the end
        return f"{base_prompt}\n\n{knowledge_section}"
    
    async def _get_knowledge_context(
        self,
        organization_id: str,
        query: str,
        domain_type: Optional[str] = None,
        source_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant knowledge chunks for a query.
        
        Args:
            organization_id: Organization ID
            query: Query to search for
            domain_type: Domain type for context
            source_type: Optional filter for source type
            
        Returns:
            List of relevant knowledge chunks
        """
        try:
            from app.services.knowledge_base_service import KnowledgeBaseService
            
            kb_service = KnowledgeBaseService()
            
            results = await kb_service.semantic_search(
                organization_id=organization_id,
                query=query,
                source_type=source_type,
                limit=self.max_context_chunks
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Failed to get knowledge context",
                organization_id=organization_id,
                error=str(e)
            )
            return []
    
    def _format_knowledge_section(
        self,
        knowledge_chunks: List[Dict[str, Any]]
    ) -> str:
        """Format knowledge chunks into a prompt section"""
        if not knowledge_chunks:
            return ""
        
        formatted_chunks = []
        total_chars = 0
        max_chars = self.max_context_tokens * 4  # Approximate chars to tokens
        
        for chunk in knowledge_chunks:
            text = chunk.get("chunkText", chunk.get("text", ""))
            source = chunk.get("sourceType", "knowledge")
            
            # Respect token limits
            if total_chars + len(text) > max_chars:
                # Truncate if needed
                remaining = max_chars - total_chars
                if remaining > 100:
                    text = text[:remaining] + "..."
                else:
                    break
            
            formatted_chunks.append(f"[{source}]: {text}")
            total_chars += len(text)
        
        if not formatted_chunks:
            return ""
        
        context = "\n\n".join(formatted_chunks)
        return f"""RELEVANT INFORMATION FROM KNOWLEDGE BASE:
{context}

Use this information to answer the customer's question accurately."""
    
    def _format_history_section(
        self,
        history: List[Dict[str, str]]
    ) -> str:
        """Format conversation history into a prompt section"""
        if not history:
            return ""
        
        # Limit to recent turns
        recent = history[-self.max_history_turns * 2:]  # Each turn has 2 messages
        
        formatted = []
        for turn in recent:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            
            if role == "user":
                formatted.append(f"Customer: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        if not formatted:
            return ""
        
        history_text = "\n".join(formatted)
        return f"""CONVERSATION HISTORY:
{history_text}"""
    
    def _get_generic_domain(self) -> DomainConfig:
        """Get a generic domain config for unknown domains"""
        from app.domains.registry import DomainType, FunctionTemplate
        
        return DomainConfig(
            domain_type=DomainType.CUSTOM,
            display_name="General Business",
            description="Generic business assistant",
            system_prompt_template="""You are {agent_name}, a helpful AI assistant for {business_name}.

You help customers with:
- Answering questions about products and services
- Providing information and assistance
- Directing customers to appropriate resources

GUIDELINES:
- Be friendly and professional
- Keep responses concise since this is a phone conversation
- If you don't have information, let the customer know
- Do not use markdown, emojis, or special formatting""",
            default_functions=[
                FunctionTemplate(
                    name="search_info",
                    description="Search for information",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    },
                    handler_type="vector_search",
                    handler_config={"source_type": "info", "limit": 5}
                ),
                FunctionTemplate(
                    name="end_call",
                    description="End the call",
                    parameters={
                        "type": "object",
                        "properties": {"reason": {"type": "string"}},
                        "required": []
                    },
                    handler_type="static",
                    handler_config={"action": "end_call"}
                )
            ],
            required_data=["business_info"],
            optional_data=["faq", "policies"]
        )
    
    async def get_agent_config_prompt(
        self,
        organization_id: str
    ) -> Optional[str]:
        """
        Get agent configuration including system prompt from database.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            System prompt from agent config or None
        """
        try:
            agents = await self.convex.query(
                "agents:getByOrganization",
                {"organizationId": organization_id}
            )
            
            if agents and len(agents) > 0:
                return agents[0].get("systemPrompt")
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to get agent config",
                organization_id=organization_id,
                error=str(e)
            )
            return None
    
    def build_function_context(
        self,
        functions: List[Dict[str, Any]]
    ) -> str:
        """
        Build a text description of available functions for the prompt.
        
        Args:
            functions: List of function definitions
            
        Returns:
            Formatted text describing available functions
        """
        if not functions:
            return ""
        
        lines = ["AVAILABLE ACTIONS:"]
        
        for func in functions:
            name = func.get("name", "unknown")
            description = func.get("description", "")
            lines.append(f"- {name}: {description}")
        
        return "\n".join(lines)


# Singleton instance
_service: Optional[PromptBuilderService] = None


def get_prompt_builder_service() -> PromptBuilderService:
    """Get the prompt builder service singleton"""
    global _service
    if _service is None:
        _service = PromptBuilderService()
    return _service
