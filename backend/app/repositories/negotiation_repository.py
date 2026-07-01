from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.negotiation import Negotiation
from app.repositories.base import BaseRepository


class NegotiationRepository(BaseRepository[Negotiation]):
    def __init__(self, db: AsyncSession):
        super().__init__(Negotiation, db)

    async def get_by_rfq(self, rfq_id: str) -> list[Negotiation]:
        result = await self.db.execute(
            select(Negotiation)
            .where(Negotiation.rfq_id == rfq_id)
            .order_by(Negotiation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_rfq_and_supplier(
        self, rfq_id: str, supplier_id: str
    ) -> list[Negotiation]:
        result = await self.db.execute(
            select(Negotiation)
            .where(
                Negotiation.rfq_id == rfq_id,
                Negotiation.supplier_id == supplier_id,
            )
            .order_by(Negotiation.round_number.asc())
        )
        return list(result.scalars().all())

    async def get_latest_round(self, rfq_id: str, supplier_id: str) -> int:
        result = await self.db.execute(
            select(func.max(Negotiation.round_number)).where(
                Negotiation.rfq_id == rfq_id,
                Negotiation.supplier_id == supplier_id,
            )
        )
        return result.scalar_one() or 0

    async def get_active_negotiations(self, rfq_id: str) -> list[Negotiation]:
        result = await self.db.execute(
            select(Negotiation).where(
                Negotiation.rfq_id == rfq_id,
                Negotiation.status.in_(["pending", "sent", "counter_received"]),
            )
        )
        return list(result.scalars().all())
