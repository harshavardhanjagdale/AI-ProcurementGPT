from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rfq import RFQ
from app.models.rfq_item import RFQItem
from app.models.rfq_supplier import RFQSupplier
from app.repositories.base import BaseRepository


class RFQRepository(BaseRepository[RFQ]):
    def __init__(self, db: AsyncSession):
        super().__init__(RFQ, db)

    async def get_with_details(self, rfq_id: str) -> RFQ | None:
        result = await self.db.execute(
            select(RFQ)
            .options(
                selectinload(RFQ.items),
                selectinload(RFQ.suppliers),
            )
            .where(RFQ.id == rfq_id)
        )
        return result.scalar_one_or_none()

    async def get_by_rfq_number(self, rfq_number: str) -> RFQ | None:
        result = await self.db.execute(
            select(RFQ).where(RFQ.rfq_number == rfq_number)
        )
        return result.scalar_one_or_none()

    async def get_user_rfqs(
        self,
        user_id: str,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[RFQ]:
        query = (
            select(RFQ)
            .options(selectinload(RFQ.items), selectinload(RFQ.suppliers))
            .where(RFQ.user_id == user_id)
        )

        if status:
            query = query.where(RFQ.status == status)

        query = query.order_by(RFQ.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def count_user_rfqs(self, user_id: str, status: str | None = None) -> int:
        query = select(func.count(RFQ.id)).where(RFQ.user_id == user_id)
        if status:
            query = query.where(RFQ.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_next_rfq_number(self) -> str:
        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
        prefix = f"RFQ-{year}-"

        result = await self.db.execute(
            select(func.count(RFQ.id)).where(RFQ.rfq_number.like(f"{prefix}%"))
        )
        count = result.scalar_one()
        return f"{prefix}{(count + 1):05d}"

    async def add_items(self, rfq_id: str, items: list[RFQItem]) -> list[RFQItem]:
        for item in items:
            item.rfq_id = rfq_id
            self.db.add(item)
        await self.db.flush()
        return items

    async def add_suppliers(self, rfq_id: str, supplier_ids: list[str]) -> list[RFQSupplier]:
        rfq_suppliers = []
        for sid in supplier_ids:
            rfq_supplier = RFQSupplier(rfq_id=rfq_id, supplier_id=sid)
            self.db.add(rfq_supplier)
            rfq_suppliers.append(rfq_supplier)
        await self.db.flush()
        return rfq_suppliers

    async def get_rfqs_by_status(self, status: str) -> list[RFQ]:
        result = await self.db.execute(
            select(RFQ).where(RFQ.status == status).order_by(RFQ.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(RFQ.status, func.count(RFQ.id)).group_by(RFQ.status)
        )
        return {row[0]: row[1] for row in result.all()}
