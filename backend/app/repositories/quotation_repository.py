from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.repositories.base import BaseRepository


class QuotationRepository(BaseRepository[Quotation]):
    def __init__(self, db: AsyncSession):
        super().__init__(Quotation, db)

    async def get_with_items(self, quotation_id: str) -> Quotation | None:
        result = await self.db.execute(
            select(Quotation)
            .options(selectinload(Quotation.items))
            .where(Quotation.id == quotation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_rfq(self, rfq_id: str) -> list[Quotation]:
        result = await self.db.execute(
            select(Quotation)
            .options(selectinload(Quotation.items), selectinload(Quotation.supplier))
            .where(Quotation.rfq_id == rfq_id)
            .order_by(Quotation.ai_score.desc())  # MySQL doesn't support NULLS LAST
        )
        return list(result.scalars().unique().all())

    async def get_by_rfq_and_supplier(self, rfq_id: str, supplier_id: str) -> Quotation | None:
        result = await self.db.execute(
            select(Quotation).where(
                Quotation.rfq_id == rfq_id,
                Quotation.supplier_id == supplier_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_items(self, quotation_id: str, items: list[QuotationItem]) -> list[QuotationItem]:
        for item in items:
            item.quotation_id = quotation_id
            self.db.add(item)
        await self.db.flush()
        return items

    async def update_scores(self, rfq_id: str, scores: list[dict]) -> None:
        """Update AI scores and rankings for quotations of an RFQ."""
        for score_data in scores:
            await self.db.execute(
                select(Quotation).where(Quotation.id == score_data["quotation_id"])
            )
            from sqlalchemy import update
            await self.db.execute(
                update(Quotation)
                .where(Quotation.id == score_data["quotation_id"])
                .values(
                    ai_score=score_data["score"],
                    ai_ranking=score_data["ranking"],
                    ai_analysis_json=score_data.get("analysis"),
                )
            )
        await self.db.flush()

    async def count_by_rfq(self, rfq_id: str) -> int:
        result = await self.db.execute(
            select(func.count(Quotation.id)).where(Quotation.rfq_id == rfq_id)
        )
        return result.scalar_one()
