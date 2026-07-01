"""
Await Replies Node - Checks for supplier email responses.
This node is designed to be used with LangGraph interrupts for async waiting.
"""
import logging

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


async def await_supplier_replies(state: ProcurementState) -> dict:
    """
    Check if supplier replies have been received.
    In production, this is an interrupt point - the graph pauses here
    and resumes when the background email worker detects replies.
    """
    rfq_id = state.get("rfq_id")

    if not rfq_id:
        return {
            "received_emails": [],
            "current_step": "await_supplier_replies",
            "error": "No RFQ ID",
        }

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from app.models.email import Email

        result = await session.execute(
            select(Email).where(
                Email.rfq_id == rfq_id,
                Email.direction == "inbound",
                Email.email_type == "supplier_reply",
            )
        )
        emails = list(result.scalars().all())

    received = [
        {
            "email_id": e.id,
            "supplier_id": e.supplier_id,
            "from_address": e.from_address,
            "subject": e.subject,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in emails
    ]

    logger.info(f"Found {len(received)} supplier replies for RFQ {rfq_id}")

    return {
        "received_emails": received,
        "current_step": "await_supplier_replies",
    }
