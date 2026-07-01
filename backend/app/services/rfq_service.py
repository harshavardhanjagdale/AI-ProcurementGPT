import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.rfq import RFQ
from app.models.rfq_item import RFQItem
from app.repositories.rfq_repository import RFQRepository
from app.schemas.rfq import (
    RFQCreate,
    RFQListResponse,
    RFQResponse,
    RFQUpdate,
)


class RFQService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RFQRepository(db)

    async def create_rfq(self, user_id: str, data: RFQCreate) -> RFQ:
        rfq_number = await self.repo.get_next_rfq_number()

        rfq = RFQ(
            rfq_number=rfq_number,
            user_id=user_id,
            title=data.title,
            description=data.description,
            budget_min=data.budget_min,
            budget_max=data.budget_max,
            currency=data.currency,
            delivery_deadline=data.delivery_deadline,
            status="draft",
        )
        rfq = await self.repo.create(rfq)

        items = [
            RFQItem(
                rfq_id=rfq.id,
                product_name=item.product_name,
                specifications=item.specifications,
                quantity=item.quantity,
                unit=item.unit,
                estimated_unit_price=item.estimated_unit_price,
            )
            for item in data.items
        ]
        await self.repo.add_items(rfq.id, items)

        if data.supplier_ids:
            await self.repo.add_suppliers(rfq.id, data.supplier_ids)

        return await self.repo.get_with_details(rfq.id)

    async def get_rfq(self, rfq_id: str) -> RFQ:
        rfq = await self.repo.get_with_details(rfq_id)
        if rfq is None:
            raise NotFoundError("RFQ", rfq_id)
        return rfq

    async def list_rfqs(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
    ) -> RFQListResponse:
        skip = (page - 1) * limit

        rfqs = await self.repo.get_user_rfqs(
            user_id=user_id, status=status, skip=skip, limit=limit
        )
        total = await self.repo.count_user_rfqs(user_id=user_id, status=status)

        return RFQListResponse(
            items=[RFQResponse.model_validate(r) for r in rfqs],
            total=total,
            page=page,
            limit=limit,
            pages=math.ceil(total / limit) if total > 0 else 0,
        )

    async def update_rfq(self, rfq_id: str, user_id: str, data: RFQUpdate) -> RFQ:
        rfq = await self.repo.get_by_id(rfq_id)
        if rfq is None:
            raise NotFoundError("RFQ", rfq_id)

        if rfq.user_id != user_id:
            raise ValidationError("You can only update your own RFQs")

        if rfq.status != "draft":
            raise ValidationError("Only draft RFQs can be updated")

        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            await self.repo.update_by_id(rfq_id, update_data)

        return await self.repo.get_with_details(rfq_id)

    async def cancel_rfq(self, rfq_id: str, user_id: str) -> RFQ:
        rfq = await self.repo.get_by_id(rfq_id)
        if rfq is None:
            raise NotFoundError("RFQ", rfq_id)

        if rfq.user_id != user_id:
            raise ValidationError("You can only cancel your own RFQs")

        if rfq.status in ("completed", "cancelled"):
            raise ValidationError(f"Cannot cancel RFQ in '{rfq.status}' status")

        await self.repo.update_by_id(rfq_id, {"status": "cancelled"})
        return await self.repo.get_with_details(rfq_id)

    async def update_status(self, rfq_id: str, new_status: str) -> RFQ:
        rfq = await self.repo.get_by_id(rfq_id)
        if rfq is None:
            raise NotFoundError("RFQ", rfq_id)

        await self.repo.update_by_id(rfq_id, {"status": new_status})
        return await self.repo.get_with_details(rfq_id)

    async def get_dashboard_stats(self, user_id: str) -> dict:
        status_counts = await self.repo.count_by_status()
        total = sum(status_counts.values())
        active_statuses = {"draft", "vendors_selected", "rfq_sent", "awaiting_quotes", "quotes_received", "analysis_complete", "negotiation"}
        active = sum(v for k, v in status_counts.items() if k in active_statuses)

        return {
            "total_rfqs": total,
            "active_rfqs": active,
            "rfqs_by_status": status_counts,
        }
