"""
Dashboard Service - Aggregates statistics across all modules
for the frontend dashboard.
"""
from datetime import date, timedelta

from sqlalchemy import select, func, case, extract, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rfq import RFQ
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.quotation import Quotation
from app.models.negotiation import Negotiation
from app.models.audit_log import AuditLog
from app.models.rfq_supplier import RFQSupplier
from app.models.workflow_session import WorkflowSession


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

    # ──────────────────────────────────────────────────────────────────────
    # Quotation Analytics
    # ──────────────────────────────────────────────────────────────────────

    async def get_quotation_analytics(self) -> dict:
        """Aggregated quotation metrics for the Quotations dashboard."""

        # Status breakdown
        status_result = await self.db.execute(
            select(Quotation.status, func.count(Quotation.id)).group_by(Quotation.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        total = sum(by_status.values())
        pending = by_status.get("received", 0) + by_status.get("under_review", 0)
        accepted = by_status.get("accepted", 0)
        rejected = by_status.get("rejected", 0)

        # Accepted value
        accepted_value_result = await self.db.execute(
            select(func.sum(Quotation.total_amount)).where(Quotation.status == "accepted")
        )
        accepted_value = float(accepted_value_result.scalar_one() or 0)

        # Monthly trend (last 6 months)
        six_months_ago = date.today() - timedelta(days=180)
        monthly_result = await self.db.execute(
            select(
                func.date_format(Quotation.created_at, '%Y-%m').label("month"),
                func.count(Quotation.id).label("count"),
                func.sum(Quotation.total_amount).label("value"),
            )
            .where(Quotation.created_at >= six_months_ago)
            .group_by(func.date_format(Quotation.created_at, '%Y-%m'))
            .order_by(func.date_format(Quotation.created_at, '%Y-%m'))
        )
        monthly_trend = [
            {"month": row[0], "count": row[1], "value": float(row[2] or 0)}
            for row in monthly_result.all()
        ]

        # Top 5 suppliers by quotation count
        top_suppliers_result = await self.db.execute(
            select(
                Supplier.name,
                func.count(Quotation.id).label("quote_count"),
            )
            .join(Supplier, Supplier.id == Quotation.supplier_id)
            .group_by(Supplier.id, Supplier.name)
            .order_by(func.count(Quotation.id).desc())
            .limit(5)
        )
        top_suppliers = [
            {"name": row[0], "count": row[1], "avg_score": 0}
            for row in top_suppliers_result.all()
        ]

        return {
            "total": total,
            "pending": pending,
            "accepted": accepted,
            "rejected": rejected,
            "accepted_value": accepted_value,
            "by_status": by_status,
            "monthly_trend": monthly_trend,
            "top_suppliers": top_suppliers,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Negotiation Analytics
    # ──────────────────────────────────────────────────────────────────────

    async def get_negotiation_analytics(self) -> dict:
        """Aggregated negotiation metrics for the Negotiations dashboard."""

        # Status breakdown
        status_result = await self.db.execute(
            select(Negotiation.status, func.count(Negotiation.id)).group_by(Negotiation.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        total = sum(by_status.values())
        active = by_status.get("pending", 0) + by_status.get("sent", 0) + by_status.get("counter_received", 0)
        completed = by_status.get("accepted", 0)
        failed = by_status.get("rejected", 0) + by_status.get("expired", 0)
        concluded = completed + failed
        success_rate = round((completed / concluded * 100), 1) if concluded > 0 else 0

        # Total savings
        savings_result = await self.db.execute(
            select(func.sum(Negotiation.original_price - Negotiation.negotiated_price))
            .where(Negotiation.status == "accepted", Negotiation.negotiated_price.is_not(None))
        )
        total_savings = float(savings_result.scalar_one() or 0)

        # Average savings percentage
        avg_savings_result = await self.db.execute(
            select(
                func.avg(
                    (Negotiation.original_price - Negotiation.negotiated_price) / Negotiation.original_price * 100
                )
            ).where(Negotiation.status == "accepted", Negotiation.negotiated_price.is_not(None))
        )
        avg_savings_pct = round(float(avg_savings_result.scalar_one() or 0), 1)

        # Average rounds
        avg_rounds_result = await self.db.execute(
            select(func.avg(Negotiation.round_number)).where(Negotiation.status == "accepted")
        )
        avg_rounds = round(float(avg_rounds_result.scalar_one() or 0), 1)

        # Monthly savings trend (last 6 months)
        six_months_ago = date.today() - timedelta(days=180)
        monthly_result = await self.db.execute(
            select(
                func.date_format(Negotiation.created_at, '%Y-%m').label("month"),
                func.sum(Negotiation.original_price - Negotiation.negotiated_price).label("savings"),
                func.count(Negotiation.id).label("count"),
            )
            .where(
                Negotiation.created_at >= six_months_ago,
                Negotiation.status == "accepted",
                Negotiation.negotiated_price.is_not(None),
            )
            .group_by(func.date_format(Negotiation.created_at, '%Y-%m'))
            .order_by(func.date_format(Negotiation.created_at, '%Y-%m'))
        )
        monthly_savings = [
            {"month": row[0], "savings": float(row[1] or 0), "count": row[2]}
            for row in monthly_result.all()
        ]

        return {
            "total": total,
            "active": active,
            "completed": completed,
            "failed": failed,
            "success_rate": success_rate,
            "total_savings": total_savings,
            "avg_savings_pct": avg_savings_pct,
            "avg_rounds": avg_rounds,
            "by_status": by_status,
            "monthly_savings": monthly_savings,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Purchase Order Analytics
    # ──────────────────────────────────────────────────────────────────────

    async def get_po_analytics(self) -> dict:
        """Aggregated PO metrics for the Purchase Orders dashboard."""

        # Status breakdown
        status_result = await self.db.execute(
            select(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        total = sum(by_status.values())
        pending_approvals = by_status.get("draft", 0)

        # Spend (approved + sent + fulfilled)
        spend_result = await self.db.execute(
            select(func.sum(PurchaseOrder.total_amount)).where(
                PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"])
            )
        )
        total_spend = float(spend_result.scalar_one() or 0)

        # Average PO value
        avg_val_result = await self.db.execute(
            select(func.avg(PurchaseOrder.total_amount))
        )
        avg_po_value = float(avg_val_result.scalar_one() or 0)

        # Tax totals
        tax_result = await self.db.execute(
            select(
                func.sum(PurchaseOrder.subtotal),
                func.sum(PurchaseOrder.tax_amount),
                func.sum(PurchaseOrder.total_amount),
            ).where(PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"]))
        )
        tax_row = tax_result.one()
        tax_breakdown = {
            "subtotal": float(tax_row[0] or 0),
            "tax": float(tax_row[1] or 0),
            "grand_total": float(tax_row[2] or 0),
        }

        # Overdue deliveries
        today = date.today()
        overdue_result = await self.db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.delivery_date < today,
                PurchaseOrder.status.in_(["draft", "approved", "sent"]),
            )
        )
        overdue = overdue_result.scalar_one()

        # Monthly spend (last 6 months)
        six_months_ago = today - timedelta(days=180)
        monthly_result = await self.db.execute(
            select(
                func.date_format(PurchaseOrder.created_at, '%Y-%m').label("month"),
                func.sum(PurchaseOrder.total_amount).label("spend"),
                func.count(PurchaseOrder.id).label("count"),
            )
            .where(PurchaseOrder.created_at >= six_months_ago)
            .group_by(func.date_format(PurchaseOrder.created_at, '%Y-%m'))
            .order_by(func.date_format(PurchaseOrder.created_at, '%Y-%m'))
        )
        monthly_spend = [
            {"month": row[0], "spend": float(row[1] or 0), "count": row[2]}
            for row in monthly_result.all()
        ]

        # Top 5 suppliers by PO value
        top_suppliers_result = await self.db.execute(
            select(
                Supplier.name,
                func.sum(PurchaseOrder.total_amount).label("total_value"),
                func.count(PurchaseOrder.id).label("po_count"),
            )
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .where(PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"]))
            .group_by(Supplier.id, Supplier.name)
            .order_by(func.sum(PurchaseOrder.total_amount).desc())
            .limit(5)
        )
        top_suppliers = [
            {"name": row[0], "value": float(row[1] or 0), "count": row[2]}
            for row in top_suppliers_result.all()
        ]

        return {
            "total": total,
            "pending_approvals": pending_approvals,
            "total_spend": total_spend,
            "avg_po_value": avg_po_value,
            "overdue": overdue,
            "by_status": by_status,
            "tax_breakdown": tax_breakdown,
            "monthly_spend": monthly_spend,
            "top_suppliers": top_suppliers,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Supplier Performance
    # ──────────────────────────────────────────────────────────────────────

    async def get_supplier_performance(self) -> dict:
        """Supplier performance metrics for Analytics page."""

        # Top suppliers by total PO value
        top_by_value = await self.db.execute(
            select(
                Supplier.id,
                Supplier.name,
                Supplier.rating,
                Supplier.country,
                func.count(PurchaseOrder.id).label("po_count"),
                func.sum(PurchaseOrder.total_amount).label("total_value"),
            )
            .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .where(PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"]))
            .group_by(Supplier.id, Supplier.name, Supplier.rating, Supplier.country)
            .order_by(func.sum(PurchaseOrder.total_amount).desc())
            .limit(10)
        )
        top_suppliers = [
            {
                "id": row[0], "name": row[1], "rating": float(row[2] or 0),
                "country": row[3], "po_count": row[4], "total_value": float(row[5] or 0),
            }
            for row in top_by_value.all()
        ]

        # Average response time (replied_at - sent_at) for suppliers that replied
        response_result = await self.db.execute(
            select(
                Supplier.name,
                func.avg(func.datediff(RFQSupplier.replied_at, RFQSupplier.sent_at)).label("avg_days"),
            )
            .join(Supplier, Supplier.id == RFQSupplier.supplier_id)
            .where(RFQSupplier.replied_at.is_not(None), RFQSupplier.sent_at.is_not(None))
            .group_by(Supplier.id, Supplier.name)
            .order_by(func.avg(func.datediff(RFQSupplier.replied_at, RFQSupplier.sent_at)))
            .limit(10)
        )
        response_times = [
            {"name": row[0], "avg_days": float(row[1] or 0)}
            for row in response_result.all()
        ]

        # Supplier win rate (POs awarded / quotations submitted)
        win_rate_result = await self.db.execute(
            select(
                Supplier.name,
                func.count(Quotation.id).label("quotes"),
                func.sum(case((Quotation.status == "accepted", 1), else_=0)).label("wins"),
            )
            .join(Supplier, Supplier.id == Quotation.supplier_id)
            .group_by(Supplier.id, Supplier.name)
            .having(func.count(Quotation.id) > 0)
            .order_by(func.sum(case((Quotation.status == "accepted", 1), else_=0)).desc())
            .limit(10)
        )
        win_rates = [
            {
                "name": row[0], "quotes": row[1], "wins": row[2],
                "rate": round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
            }
            for row in win_rate_result.all()
        ]

        return {
            "top_suppliers": top_suppliers,
            "response_times": response_times,
            "win_rates": win_rates,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Procurement Overview (for Analytics page)
    # ──────────────────────────────────────────────────────────────────────

    async def get_procurement_overview(self) -> dict:
        """Cross-cutting analytics for the executive Analytics page."""

        # Monthly spend trend (last 12 months)
        twelve_months_ago = date.today() - timedelta(days=365)
        spend_trend = await self.db.execute(
            select(
                func.date_format(PurchaseOrder.created_at, '%Y-%m').label("month"),
                func.sum(PurchaseOrder.total_amount).label("spend"),
            )
            .where(PurchaseOrder.created_at >= twelve_months_ago,
                   PurchaseOrder.status.in_(["approved", "sent", "acknowledged", "fulfilled"]))
            .group_by(func.date_format(PurchaseOrder.created_at, '%Y-%m'))
            .order_by(func.date_format(PurchaseOrder.created_at, '%Y-%m'))
        )
        monthly_spend = [{"month": r[0], "spend": float(r[1] or 0)} for r in spend_trend.all()]

        # Workflow efficiency
        workflow_result = await self.db.execute(
            select(
                func.count(WorkflowSession.id),
                func.sum(case((WorkflowSession.status == "completed", 1), else_=0)),
                func.sum(case((WorkflowSession.status == "failed", 1), else_=0)),
                func.sum(case((WorkflowSession.status == "cancelled", 1), else_=0)),
            )
        )
        wf_row = workflow_result.one()
        workflow_stats = {
            "total": wf_row[0] or 0,
            "completed": int(wf_row[1] or 0),
            "failed": int(wf_row[2] or 0),
            "cancelled": int(wf_row[3] or 0),
        }

        # Average cycle time (completed sessions only)
        cycle_result = await self.db.execute(
            select(
                func.avg(func.datediff(WorkflowSession.completed_at, WorkflowSession.started_at))
            ).where(
                WorkflowSession.status == "completed",
                WorkflowSession.completed_at.is_not(None),
                WorkflowSession.started_at.is_not(None),
            )
        )
        avg_cycle_days = float(cycle_result.scalar_one() or 0)

        return {
            "monthly_spend": monthly_spend,
            "workflow_stats": workflow_stats,
            "avg_cycle_days": round(avg_cycle_days, 1),
        }
