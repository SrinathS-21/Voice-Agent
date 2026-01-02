"""
Repository for catalog items (products, menu items, services, etc.)
Domain-agnostic - works with any type of inventory items.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class CatalogItem:
    """Generic catalog item model"""
    id: str
    name: str
    category: str
    description: str
    price: float
    tags: List[str]
    metadata: dict


class CatalogRepository:
    """
    Repository for catalog/inventory items.
    Provides database access for structured item data.
    Can be used alongside RAG for hybrid search.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_name(self, name: str) -> Optional[dict]:
        """Search for item by name (partial match)"""
        # Note: This would need a proper model defined
        # For now, most retrieval goes through RAG
        logger.warning("CatalogRepository.get_by_name called - consider using RAG search instead")
        return None

    async def list_by_category(self, category: str) -> List[dict]:
        """List items by category"""
        logger.warning("CatalogRepository.list_by_category called - consider using RAG search instead")
        return []

    async def search(self, term: str, category: Optional[str] = None) -> List[dict]:
        """Search items by term and optional category"""
        logger.warning("CatalogRepository.search called - consider using RAG search instead")
        return []

    async def list_all(self, limit: int = 100) -> List[dict]:
        """List all items with optional limit"""
        logger.warning("CatalogRepository.list_all called - consider using RAG search instead")
        return []


# Backward compatibility alias
MenuRepository = CatalogRepository
