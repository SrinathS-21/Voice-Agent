"""
Voice Knowledge Service
Optimized knowledge retrieval service for voice agents with caching and low-latency responses.
Domain-agnostic - works with any type of business content.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import json
import re

from app.core.logging import get_logger
from app.core.convex_client import get_convex_client

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL tracking"""
    data: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.
    Optimized for high-frequency voice agent queries.
    """
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache, return None if not found or expired"""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check TTL
            if time.time() - entry.created_at > self.ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access stats and move to end (most recently used)
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._cache.move_to_end(key)
            self._hits += 1
            
            return entry.data
    
    async def set(self, key: str, value: Any) -> None:
        """Set item in cache"""
        async with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = CacheEntry(
                data=value,
                created_at=time.time()
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }


class VoiceKnowledgeService:
    """
    Optimized knowledge service for voice agents.
    Domain-agnostic - works with any type of business content.
    
    Features:
    - Multi-level caching (embedding cache, result cache)
    - Parallel search across catalog and knowledge
    - Latency-optimized response formatting
    - Category-aware filtering
    """
    
    # Class-level caches (shared across instances)
    _embedding_cache = LRUCache(max_size=1000, ttl_seconds=3600)  # 1 hour
    _result_cache = LRUCache(max_size=500, ttl_seconds=300)  # 5 minutes
    
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.convex_client = get_convex_client()
        
        # Organization-specific caches
        self._org_context_cache: Dict[str, Tuple[float, Any]] = {}
        self._org_cache_ttl = 600  # 10 minutes
    
    @classmethod
    async def invalidate_cache(cls, organization_id: Optional[str] = None) -> None:
        """
        Invalidate caches when knowledge base is updated.
        Called by SmartIngestionService after document ingestion.
        """
        # Clear result cache (which depends on knowledge base content)
        cls._result_cache = LRUCache(max_size=500, ttl_seconds=300)
        logger.info(f"Invalidated result cache for org: {organization_id or 'all'}")
    
    async def search_items(
        self,
        query: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Fast semantic search for items/products using RAG.
        Optimized for voice agent function calls.
        Works with any domain: products, menu items, services, rooms, etc.
        Pure semantic search - no filters needed.
        """
        start_time = time.time()
        cache_key = f"items:{self.organization_id}:{query}:{limit}"
        
        # Check result cache
        cached = await self._result_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for items search: {query}")
            return cached
        
        try:
            # Pure semantic search - no filters
            args = {
                "namespace": self.organization_id,
                "query": query,
                "limit": limit,
                "minScore": 0.20  # Lower threshold for better recall
            }
            
            results = await self.convex_client.action("rag:search", args)
            
            # FIXED: Consistently use 'results' field which has scores
            raw_results = results.get("results", [])
            logger.info(f"RAG search returned {len(raw_results)} results for query: {query}")
            
            if not raw_results:
                response = {
                    "found": False,
                    "message": f"No items found matching '{query}'",
                    "suggestions": ["Try a different search term", "Ask about categories"]
                }
            else:
                # Format for voice response (concise)
                items = []
                
                for item in raw_results:
                    text = item.get("text", "")
                    score = item.get("score", 0)
                    
                    # Parse enriched text format: "Category: X | Name: Y | Price: $Z | Description: ..."
                    parsed = self._parse_enriched_text(text)
                    
                    items.append({
                        "name": parsed.get("name", "Item"),
                        "price": parsed.get("price", 0),
                        "description": parsed.get("description", text[:200]),
                        "category": parsed.get("category", ""),
                        "tags": parsed.get("tags", []),
                        "score": score
                    })
                
                response = {
                    "found": True,
                    "count": len(items),
                    "items": items
                }
            
            # Cache result
            await self._result_cache.set(cache_key, response)
            
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"Items search completed in {latency_ms:.0f}ms: {query}")
            
            return response
            
        except Exception as e:
            logger.error(f"Items search failed: {str(e)}")
            return {
                "found": False,
                "error": "Search temporarily unavailable",
                "message": "Please try again or ask about specific items"
            }
    
    def _parse_enriched_text(self, text: str) -> Dict[str, Any]:
        """
        Parse enriched text format created by SmartIngestionService.
        Format: "Category: X | Name: Y | Price: $Z | Description: ..."
        Falls back to regex extraction for legacy data.
        """
        result = {
            "name": "",
            "category": "",
            "price": 0,
            "description": "",
            "tags": []
        }
        
        # Try parsing pipe-separated enriched format
        if " | " in text:
            parts = text.split(" | ")
            for part in parts:
                if ": " in part:
                    key, value = part.split(": ", 1)
                    key = key.lower().strip()
                    value = value.strip()
                    
                    if key == "name":
                        result["name"] = value
                    elif key == "category":
                        result["category"] = value
                    elif key == "price":
                        # Extract numeric price
                        price_match = re.search(r'\$?([\d]+\.?\d*)', value)
                        if price_match:
                            try:
                                result["price"] = float(price_match.group(1))
                            except ValueError:
                                pass
                    elif key == "description":
                        result["description"] = value
                    elif key == "tags":
                        result["tags"] = [t.strip() for t in value.split(",")]
            
            if result["name"]:
                return result
        
        # Fallback: regex extraction for legacy/unstructured data
        # Pattern 1: "Name – $Price" or "Name - $Price"  
        match = re.match(r"^(.*?)\s*[–-]\s*\$?([\d\.]+)", text)
        if match:
            result["name"] = self._clean_name(match.group(1).strip())
            try:
                result["price"] = float(match.group(2))
            except ValueError:
                pass
        else:
            # Pattern 2: Look for "ItemName costs $X" or "ItemName is priced at $X"
            price_pattern = re.search(r'([A-Z][A-Za-z\s]+)\s+(?:costs?|is priced at|priced at)\s+\$?([\d]+\.[\d]{2})', text)
            if price_pattern:
                result["name"] = self._clean_name(price_pattern.group(1).strip())
                try:
                    result["price"] = float(price_pattern.group(2))
                except ValueError:
                    pass
            else:
                # Pattern 3: Look for "$Price ItemName" or "ItemName $Price"
                item_pattern = re.search(r'(?:\$?([\d]+\.[\d]{2})\s+([A-Z][A-Za-z\s]+))|(?:([A-Z][A-Za-z\s]+)\s+\$?([\d]+\.[\d]{2}))', text)
                if item_pattern:
                    if item_pattern.group(1):  # "$Price Name" format
                        result["price"] = float(item_pattern.group(1))
                        result["name"] = self._clean_name(item_pattern.group(2).strip())
                    elif item_pattern.group(3):  # "Name $Price" format
                        result["name"] = self._clean_name(item_pattern.group(3).strip())
                        try:
                            result["price"] = float(item_pattern.group(4))
                        except:
                            pass
                else:
                    # Pattern 4: First complete capitalized phrase as name
                    cap_match = re.search(r'([A-Z][A-Za-z]+(?:\s+[A-Z]?[a-z]+)*)', text)
                    if cap_match:
                        potential_name = cap_match.group(1).strip()
                        # Make sure it's not a fragment (too short or a common word)
                        if len(potential_name) > 3 and potential_name.lower() not in ['menu', 'the', 'and', 'for', 'with']:
                            result["name"] = self._clean_name(potential_name)
                    
                    # Try to find price anywhere in text
                    price_match = re.search(r'\$?([\d]+\.[\d]{2})', text)
                    if price_match:
                        try:
                            result["price"] = float(price_match.group(1))
                        except ValueError:
                            pass
        
        result["description"] = self._clean_description(text[:200]) if text else ""
        return result
    
    def _clean_name(self, name: str) -> str:
        """Clean markdown and formatting from item names."""
        if not name:
            return ""
        # Remove markdown symbols
        name = re.sub(r'^[\|\-•*#]+\s*', '', name)  # Start of string
        name = re.sub(r'\s*[\|#]+\s*$', '', name)   # End of string  
        name = re.sub(r'\*+', '', name)              # Asterisks anywhere
        name = re.sub(r'^#+\s*', '', name)           # Headers
        # Remove section headers like "Veg Starters Menu\n\n"
        name = re.sub(r'^[A-Za-z\s]+Menu\s*\n+', '', name)
        # Remove newlines and extra whitespace
        name = re.sub(r'\s*\n+\s*', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        return name
    
    def _clean_description(self, desc: str) -> str:
        """Clean markdown and formatting from descriptions for voice output."""
        if not desc:
            return ""
        # Remove markdown table syntax
        desc = re.sub(r'\|', ' ', desc)
        # Remove markdown headers
        desc = re.sub(r'#+\s*', '', desc)
        # Remove asterisks (bold/italic)
        desc = re.sub(r'\*+', '', desc)
        # Remove bullet points
        desc = re.sub(r'^[-•]\s*', '', desc, flags=re.MULTILINE)
        # Clean up whitespace
        desc = re.sub(r'\s+', ' ', desc)
        return desc.strip()
    async def search_knowledge(
        self,
        query: str,
        limit: int = 3
    ) -> Dict[str, Any]:
        """
        Search knowledge base for FAQ, policies, information, etc.
        Returns formatted response for voice output.
        Pure semantic search - no filters needed.
        """
        start_time = time.time()
        cache_key = f"know:{self.organization_id}:{query}:{limit}"
        
        cached = await self._result_cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Pure semantic search - no filters
            args = {
                "namespace": self.organization_id,
                "query": query,
                "limit": limit,
                "minScore": 0.25
            }

            results = await self.convex_client.action("rag:search", args)
            
            # FIXED: Consistently use 'results' field
            raw_results = results.get("results", [])
            
            if not raw_results:
                response = {
                    "found": False,
                    "answer": "I don't have specific information about that."
                }
            else:
                # Combine top results into a coherent answer
                texts = []
                for r in raw_results[:2]:
                    text = r.get("text", "")
                    # Parse enriched format if present
                    if " | " in text:
                        parsed = self._parse_enriched_text(text)
                        if parsed.get("description"):
                            texts.append(parsed["description"])
                        elif parsed.get("answer"):
                            texts.append(parsed["answer"])
                        else:
                            texts.append(text)
                    else:
                        texts.append(text)
                
                combined = " ".join(texts)[:500]  # Limit for voice
                
                response = {
                    "found": True,
                    "answer": combined,
                    "source_count": len(raw_results)
                }
            
            await self._result_cache.set(cache_key, response)
            
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"Knowledge search completed in {latency_ms:.0f}ms: {query}")
            
            return response
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {str(e)}")
            return {
                "found": False,
                "error": "Knowledge search unavailable"
            }
    
    async def get_business_info(
        self,
        info_type: str
    ) -> Dict[str, Any]:
        """
        Get business information (hours, location, policies).
        Uses cached organization data for fast responses.
        """
        # Check org context cache
        cache_entry = self._org_context_cache.get(self.organization_id)
        if cache_entry and (time.time() - cache_entry[0] < self._org_cache_ttl):
            org_data = cache_entry[1]
        else:
            # Fetch from database
            try:
                org_data = await self.convex_client.query(
                    "organizations:getById",
                    {"id": self.organization_id}
                )
                if org_data:
                    self._org_context_cache[self.organization_id] = (time.time(), org_data)
            except Exception as e:
                logger.error(f"Failed to fetch org data: {e}")
                org_data = None
        
        # Try to get from config JSON if available
        if org_data and org_data.get("config"):
            try:
                config = json.loads(org_data["config"])
                business = config.get("business", {})
                
                if info_type == "hours":
                    hours = business.get("hours", {})
                    if hours:
                        return {"found": True, "hours": hours}
                
                elif info_type == "location":
                    contact = business.get("contact", {})
                    if contact.get("address"):
                        return {
                            "found": True,
                            "address": contact["address"],
                            "phone": contact.get("phone", "")
                        }
                
                elif info_type == "contact":
                    contact = business.get("contact", {})
                    if contact:
                        return {"found": True, "contact": contact}
                
                elif info_type == "policies":
                    policies = config.get("policies", {})
                    if policies:
                        return {"found": True, "policies": policies}
                
                elif info_type == "features":
                    features = business.get("features", [])
                    if features:
                        return {"found": True, "features": features}
                        
            except json.JSONDecodeError:
                pass
        
        # Fallback to knowledge search
        return await self.search_knowledge(f"business {info_type}")
    
    async def hybrid_search(
        self,
        query: str,
        include_items: bool = True,
        include_knowledge: bool = True,
        category: Optional[str] = None,
        items_limit: int = 3,
        knowledge_limit: int = 2
    ) -> Dict[str, Any]:
        """
        Combined search across items/catalog and knowledge base.
        Runs searches in parallel for lowest latency.
        Supports category filtering for domain-agnostic retrieval.
        """
        start_time = time.time()
        
        tasks = []
        if include_items:
            tasks.append(("items", self.search_items(query, category=category, limit=items_limit)))
        if include_knowledge:
            tasks.append(("knowledge", self.search_knowledge(query, category=category, limit=knowledge_limit)))
        
        if not tasks:
            return {"results": {}}
        
        # Run all searches in parallel
        results_list = await asyncio.gather(
            *[t[1] for t in tasks],
            return_exceptions=True
        )
        
        # Combine results
        combined = {}
        for (name, _), result in zip(tasks, results_list):
            if isinstance(result, Exception):
                logger.error(f"Search task {name} failed: {result}")
                combined[name] = {"found": False, "error": str(result)}
            else:
                combined[name] = result
        
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Hybrid search completed in {latency_ms:.0f}ms: {query}")
        
        return {
            "results": combined,
            "latency_ms": latency_ms
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get all cache statistics"""
        return {
            "embedding_cache": self._embedding_cache.get_stats(),
            "result_cache": self._result_cache.get_stats()
        }


# Service instance cache
_service_instances: Dict[str, VoiceKnowledgeService] = {}


def get_voice_knowledge_service(organization_id: str) -> VoiceKnowledgeService:
    """
    Get or create a VoiceKnowledgeService instance for an organization.
    Reuses instances for cache efficiency.
    """
    if organization_id not in _service_instances:
        _service_instances[organization_id] = VoiceKnowledgeService(organization_id)
    return _service_instances[organization_id]


def clear_service_cache(organization_id: Optional[str] = None) -> None:
    """Clear service instance cache"""
    global _service_instances
    if organization_id:
        _service_instances.pop(organization_id, None)
    else:
        _service_instances.clear()
