"""
Repository for menu items
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.models.database import MenuItem
from app.core.logging import get_logger

logger = get_logger(__name__)


class MenuRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_name(self, name: str) -> Optional[MenuItem]:
        q = select(MenuItem).where(MenuItem.name.ilike(f"%{name}%"))
        res = await self.db.execute(q)
        return res.scalars().first()

    async def list_by_category(self, category: str) -> List[MenuItem]:
        q = select(MenuItem).where(MenuItem.category.ilike(category))
        res = await self.db.execute(q)
        return res.scalars().all()

    async def search(self, term: str) -> List[MenuItem]:
        q = select(MenuItem).where(MenuItem.name.ilike(f"%{term}%"))
        res = await self.db.execute(q)
        return res.scalars().all()

    async def list_all(self) -> List[MenuItem]:
        q = select(MenuItem)
        res = await self.db.execute(q)
        return res.scalars().all()
