from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.supplier import Supplier
from app.models.supplier_category import SupplierCategory
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, db: AsyncSession):
        super().__init__(Supplier, db)

    async def get_by_email(self, email: str) -> Supplier | None:
        result = await self.db.execute(
            select(Supplier).where(Supplier.email == email)
        )
        return result.scalar_one_or_none()

    async def get_with_categories(self, supplier_id: str) -> Supplier | None:
        result = await self.db.execute(
            select(Supplier)
            .options(selectinload(Supplier.categories))
            .where(Supplier.id == supplier_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        category: str | None = None,
        country: str | None = None,
        min_rating: float | None = None,
        status: str = "active",
        skip: int = 0,
        limit: int = 20,
    ) -> list[Supplier]:
        query = (
            select(Supplier)
            .options(selectinload(Supplier.categories))
            .where(Supplier.status == status)
        )

        if country:
            query = query.where(Supplier.country == country)
        if min_rating is not None:
            query = query.where(Supplier.rating >= min_rating)
        if category:
            query = query.join(Supplier.categories).where(
                SupplierCategory.category_name.ilike(f"%{category}%")
            )

        query = query.order_by(Supplier.rating.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def count_filtered(
        self,
        category: str | None = None,
        country: str | None = None,
        min_rating: float | None = None,
        status: str = "active",
    ) -> int:
        query = select(func.count(Supplier.id)).where(Supplier.status == status)

        if country:
            query = query.where(Supplier.country == country)
        if min_rating is not None:
            query = query.where(Supplier.rating >= min_rating)
        if category:
            query = query.join(Supplier.categories).where(
                SupplierCategory.category_name.ilike(f"%{category}%")
            )

        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_by_ids(self, supplier_ids: list[str]) -> list[Supplier]:
        result = await self.db.execute(
            select(Supplier)
            .options(selectinload(Supplier.categories))
            .where(Supplier.id.in_(supplier_ids))
        )
        return list(result.scalars().unique().all())

    async def get_active_by_categories(self, categories: list[str], limit: int = 10) -> list[Supplier]:
        query = (
            select(Supplier)
            .options(selectinload(Supplier.categories))
            .join(Supplier.categories)
            .where(
                Supplier.status == "active",
                or_(*[SupplierCategory.category_name.ilike(f"%{cat}%") for cat in categories])
            )
            .order_by(Supplier.rating.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())
