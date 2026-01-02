"""
Knowledge Base Service
Handles semantic search and context retrieval from the knowledge base.
Domain-agnostic - works with any type of business content.
"""

from typing import List, Dict, Optional, Any
from app.core.convex_client import get_convex_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeBaseService:
    """Service for interacting with the knowledge base"""
    
    def __init__(self, organization_id: str):
        """
        Initialize knowledge base service for an organization
        
        Args:
            organization_id: The organization identifier
        """
        self.organization_id = organization_id
        self.convex_client = get_convex_client()
        
        logger.info(f"KnowledgeBaseService initialized for organization: {organization_id}")
    
    async def search_catalog(
        self,
        query: str,
        category: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search catalog/items semantically using RAG.
        Works for any domain: products, menu items, services, rooms, etc.
        
        Args:
            query: Search query
            category: Optional category filter (e.g., "starters", "electronics", "rooms")
            source_type: Optional source type filter (e.g., "catalog", "menu")
            limit: Maximum results to return
        """
        try:
            args = {
                "namespace": self.organization_id,
                "query": query,
                "limit": limit,
                "minScore": 0.25  # Lower threshold for better recall
            }
            
            # Add filters if provided
            if source_type:
                args["sourceType"] = source_type
            if category:
                args["category"] = category.lower()
            
            # Perform vector search via Convex RAG action
            results = await self.convex_client.action("rag:search", args)
            
            # Use 'results' field which contains scores
            mapped_results = []
            raw_results = results.get("results", [])
            
            for item in raw_results:
                mapped_results.append({
                    "text": item.get("text", ""),
                    "description": item.get("text", ""),
                    "_score": item.get("score", 0),
                    "entryId": item.get("entryId"),
                    "sourceType": source_type or "catalog"
                })
            
            logger.info(f"Catalog search for '{query}' returned {len(mapped_results)} results")
            return mapped_results
            
        except Exception as e:
            logger.error(f"Catalog search failed: {str(e)}")
            return []
    
    # Backward compatibility alias
    async def search_menu(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Deprecated: Use search_catalog instead.
        Maintained for backward compatibility.
        """
        logger.warning("search_menu is deprecated, use search_catalog instead")
        return await self.search_catalog(
            query=query,
            category=category,
            source_type="catalog",
            limit=limit
        )
    
    async def search_knowledge(
        self,
        query: str,
        source_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.25
    ) -> List[Dict[str, Any]]:
        """
        Search general knowledge base semantically using RAG.
        Works for FAQ, policies, information, etc.
        """
        try:
            args = {
                "namespace": self.organization_id,
                "query": query,
                "limit": limit,
                "minScore": min_score
            }
            if source_type:
                args["sourceType"] = source_type
            if category:
                args["category"] = category.lower()

            results = await self.convex_client.action("rag:search", args)
            
            # Use 'results' field consistently
            mapped_results = []
            raw_results = results.get("results", [])
            
            for item in raw_results:
                mapped_results.append({
                    "chunkText": item.get("text", ""),
                    "text": item.get("text", ""),
                    "_score": item.get("score", 0),
                    "entryId": item.get("entryId"),
                    "sourceType": source_type or "general"
                })
            
            logger.info(
                f"Knowledge search for '{query}' returned {len(mapped_results)} results "
                f"(source_type: {source_type}, category: {category})"
            )
            return mapped_results
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {str(e)}")
            return []
    
    async def retrieve_context(
        self,
        query: str,
        max_chunks: int = 5,
        include_catalog: bool = True,
        include_knowledge: bool = True
    ) -> str:
        """
        Retrieve relevant context for a query.
        Combines catalog search and knowledge base search results.
        
        Args:
            query: The user's query
            max_chunks: Maximum number of context chunks to retrieve
            include_catalog: Whether to search catalog items
            include_knowledge: Whether to search general knowledge
            
        Returns:
            Formatted context string ready for LLM injection
        """
        context_parts = []
        
        try:
            # Search catalog items if enabled
            if include_catalog:
                catalog_results = await self.search_catalog(query, limit=max_chunks)
                
                if catalog_results:
                    catalog_context = "RELEVANT ITEMS:\n"
                    for item in catalog_results[:3]:
                        text = item.get('text', item.get('description', ''))
                        score = item.get('_score', 0)
                        catalog_context += f"- {text} (relevance: {score:.2f})\n"
                    context_parts.append(catalog_context)
            
            # Search general knowledge if enabled
            if include_knowledge:
                knowledge_results = await self.search_knowledge(query, limit=max_chunks)
                
                if knowledge_results:
                    knowledge_context = "RELEVANT INFORMATION:\n"
                    for chunk in knowledge_results:
                        text = chunk.get('chunkText', chunk.get('text', ''))
                        score = chunk.get('_score', 0)
                        source_type = chunk.get('sourceType', 'general')
                        knowledge_context += f"- [{source_type}] {text} (relevance: {score:.2f})\n"
                    context_parts.append(knowledge_context)
            
            if context_parts:
                full_context = "\n".join(context_parts)
                logger.info(f"Retrieved context for query '{query}': {len(full_context)} chars")
                return full_context
            else:
                logger.info(f"No context found for query '{query}'")
                return ""
                
        except Exception as e:
            logger.error(f"Context retrieval failed: {str(e)}")
            return ""
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge base
        
        Returns:
            Dictionary with stats (chunk count by source type, etc.)
        """
        try:
            # Get total chunk count via RAG list
            # We use listEntries with a small limit just to check connection, or we'd need a count action.
            # convex-rag doesn't expose strict "count", but we can use listEntries.
            # Actually, `rag.list` returns a page.
            
            result = await self.convex_client.action(
                "rag:listEntries",
                {"namespace": self.organization_id, "limit": 1000}
            )
            
            total_chunks = len(result.get("entries", [])) if result else 0
            if result.get("hasMore"):
                 total_chunks = str(total_chunks) + "+"
            
            stats = {
                "organizationId": self.organization_id,
                "totalChunks": total_chunks,
                "embeddingDimensions": 1536
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get knowledge stats: {str(e)}")
            return {
                "organizationId": self.organization_id,
                "totalChunks": 0,
                "error": str(e)
            }


def get_knowledge_base_service(organization_id: str) -> KnowledgeBaseService:
    """
    Create a knowledge base service instance for an organization
    
    Args:
        organization_id: The organization identifier
        
    Returns:
        KnowledgeBaseService instance
    """
    return KnowledgeBaseService(organization_id)
