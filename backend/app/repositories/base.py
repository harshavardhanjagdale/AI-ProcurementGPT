from typing import Any, Generic, Type, TypeVar

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, entity_id: str) -> ModelType | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        order_by: Any = None,
    ) -> list[ModelType]:
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        if order_by is not None:
            query = query.order_by(order_by)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def create(self, entity: ModelType) -> ModelType:
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update_by_id(self, entity_id: str, data: dict[str, Any]) -> ModelType | None:
        await self.db.execute(
            update(self.model).where(self.model.id == entity_id).values(**data)
        )
        await self.db.flush()
        return await self.get_by_id(entity_id)

    async def delete_by_id(self, entity_id: str) -> bool:
        result = await self.db.execute(
            delete(self.model).where(self.model.id == entity_id)
        )
        await self.db.flush()
        return result.rowcount > 0
