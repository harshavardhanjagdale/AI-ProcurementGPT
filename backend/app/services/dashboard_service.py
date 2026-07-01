"""
Dashboard Service - Aggregates statistics across all modules
for the frontend dashboard.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rfq import RFQ
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.quotation import Quotation
from app.models.negotiation import Negotiation
from app.models.audit_log import AuditLog


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self) -> dict:
        """Get overview dashboard statistics."""
        # RFQ stats
        rfq_count_result = await self.db.execute(select(func.count(RFQ.id)))
        total_rfqs = rfq_count_result.scalar_one()

        rfq_status_result = await self.db.execute(
            select(RFQ.status, func.count(RFQ.id)).group_by(RFQ.status)
        )
        rfqs_by_status = {row[0]: row[1] for row in rfq_status_result.all()}

        active_statuses = {"draft", "vendors_selected", "rfq_sent", "awaiting_quotes", "quotes_received", "analysis_complete", "negotiation"}
        active_rfqs = sum(v for k, v in rfqs_by_status.items() if k in active_statuses)

        # Supplier stats
        supplier_count_result = await self.db.execute(
            select(func.count(Supplier.id)).where(Supplier.status == "active")
        )
        total_suppliers = supplier_count_result.scalar_one()

        # PO stats
        po_value_result = await self.db.execute(
            select(func.sum(PurchaseOrder.total_amount)).where(
                PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"])
            )
        )
        total_po_value = float(po_value_result.scalar_one() or 0)

        po_count_result = await self.db.execute(select(func.count(PurchaseOrder.id)))
        total_pos = po_count_result.scalar_one()

        # Quotation stats
        quotation_count_result = await self.db.execute(select(func.count(Quotation.id)))
        total_quotations = quotation_count_result.scalar_one()

        # Negotiation savings
        savings_result = await self.db.execute(
            select(
                func.sum(Negotiation.original_price - Negotiation.negotiated_price)
            ).where(
                Negotiation.status == "accepted",
                Negotiation.negotiated_price.is_not(None),
            )
        )
        total_savings = float(savings_result.scalar_one() or 0)

        return {
            "total_rfqs": total_rfqs,
            "active_rfqs": active_rfqs,
            "total_suppliers": total_suppliers,
            "total_purchase_orders": total_pos,
            "total_po_value": total_po_value,
            "total_quotations": total_quotations,
            "negotiation_savings": total_savings,
            "rfqs_by_status": rfqs_by_status,
            "avg_cycle_time_days": None,
        }

    async def get_recent_activity(self, limit: int = 10) -> list[dict]:
        """Get recent audit log entries."""
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        logs = list(result.scalars().all())

        return [
            {
                "id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    async def get_rfq_pipeline(self) -> list[dict]:
        """Get RFQ pipeline (count by status for funnel visualization)."""
        result = await self.db.execute(
            select(RFQ.status, func.count(RFQ.id)).group_by(RFQ.status)
        )

        pipeline_order = [
            "draft", "vendors_selected", "rfq_sent", "awaiting_quotes",
            "quotes_received", "analysis_complete", "negotiation",
            "po_generated", "completed", "cancelled",
        ]

        status_counts = {row[0]: row[1] for row in result.all()}

        return [
            {"status": status, "count": status_counts.get(status, 0)}
            for status in pipeline_order
        ]
