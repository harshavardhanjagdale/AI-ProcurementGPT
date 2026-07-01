"""
Create RFQ Node - Persists the parsed RFQ data to the database
so downstream nodes (email, quotations, PO) have a real record to reference.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.models.rfq import RFQ
from app.models.rfq_item import RFQItem
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


async def create_rfq_record(state: ProcurementState) -> dict:
    """Create the RFQ and its items in MySQL from parsed intent."""
    parsed = state["parsed_intent"]
    user_id = state["user_id"]
    workflow_id = state.get("workflow_run_id", "")

    title = parsed.get("title", "Untitled RFQ")
    description = parsed.get("description", "")
    items = parsed.get("items", [])
    budget_min = parsed.get("budget_min")
    budget_max = parsed.get("budget_max")
    currency = parsed.get("currency", "USD")
    delivery_days = parsed.get("delivery_deadline_days")

    delivery_deadline = None
    if delivery_days:
        delivery_deadline = datetime.now(timezone.utc) + timedelta(days=delivery_days)

    async with AsyncSessionLocal() as session:
        rfq_id = generate_uuid()

        # Generate RFQ number
        year = datetime.now(timezone.utc).year
        result = await session.execute(
            select(func.count(RFQ.id)).where(RFQ.rfq_number.like(f"RFQ-{year}-%"))
        )
        count = result.scalar() or 0
        rfq_number = f"RFQ-{year}-{count + 1:05d}"

        rfq = RFQ(
            id=rfq_id,
            rfq_number=rfq_number,
            user_id=user_id,
            title=title,
            description=description,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency,
            delivery_deadline=delivery_deadline,
            status="draft",
            ai_workflow_id=workflow_id,
        )
        session.add(rfq)

        for item_data in items:
            rfq_item = RFQItem(
                id=generate_uuid(),
                rfq_id=rfq_id,
                product_name=item_data.get("product_name", ""),
                specifications=item_data.get("specifications"),
                quantity=item_data.get("quantity", 1),
                unit=item_data.get("unit", "units"),
            )
            session.add(rfq_item)

        await session.commit()
        logger.info(f"Created RFQ {rfq_number} (id={rfq_id}) with {len(items)} items")

    return {
        "rfq_id": rfq_id,
        "current_step": "create_rfq_record",
    }
