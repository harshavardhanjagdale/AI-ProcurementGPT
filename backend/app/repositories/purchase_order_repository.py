from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase_order import PurchaseOrder
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    def __init__(self, db: AsyncSession):
        super().__init__(PurchaseOrder, db)

    async def get_with_items(self, po_id: str) -> PurchaseOrder | None:
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.id == po_id)
        )
        return result.scalar_one_or_none()

    async def get_by_po_number(self, po_number: str) -> PurchaseOrder | None:
        result = await self.db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )
        return result.scalar_one_or_none()

    async def get_by_rfq(self, rfq_id: str) -> list[PurchaseOrder]:
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.rfq_id == rfq_id)
            .order_by(PurchaseOrder.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_user_pos(
        self,
        user_id: str,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[PurchaseOrder]:
        query = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.user_id == user_id)
        )
        if status:
            query = query.where(PurchaseOrder.status == status)
        query = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def count_user_pos(self, user_id: str, status: str | None = None) -> int:
        query = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.user_id == user_id)
        if status:
            query = query.where(PurchaseOrder.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_next_po_number(self) -> str:
        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
        prefix = f"PO-{year}-"
        result = await self.db.execute(
            select(func.count(PurchaseOrder.id)).where(PurchaseOrder.po_number.like(f"{prefix}%"))
        )
        count = result.scalar_one()
        return f"{prefix}{(count + 1):05d}"

    async def get_total_value(self, user_id: str | None = None) -> float:
        query = select(func.sum(PurchaseOrder.total_amount))
        if user_id:
            query = query.where(PurchaseOrder.user_id == user_id)
        query = query.where(PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"]))
        result = await self.db.execute(query)
        return float(result.scalar_one() or 0)
