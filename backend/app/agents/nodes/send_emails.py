"""
Send Emails Node - Sends generated RFQ emails to all selected suppliers via SMTP.
"""
import logging

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


async def send_rfq_emails(state: ProcurementState) -> dict:
    """Send RFQ emails to all selected suppliers."""
    rfq_id = state.get("rfq_id")
    suppliers = state.get("selected_suppliers", [])
    user_id = state.get("user_id")

    if not rfq_id or not suppliers:
        return {
            "rfq_emails_sent": False,
            "current_step": "send_rfq_emails",
            "error": "Missing RFQ ID or suppliers",
        }

    supplier_ids = [s["id"] for s in suppliers]

    async with AsyncSessionLocal() as session:
        try:
            service = EmailService(session)
            results = await service.send_rfq_emails(
                rfq_id=rfq_id,
                supplier_ids=supplier_ids,
                sender_name="Procurement Team",
            )
            await session.commit()

            sent_count = sum(1 for r in results if r["success"])
            logger.info(f"Sent {sent_count}/{len(results)} RFQ emails for {rfq_id}")

            return {
                "rfq_emails_sent": sent_count > 0,
                "current_step": "send_rfq_emails",
            }
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to send RFQ emails: {e}")
            return {
                "rfq_emails_sent": False,
                "current_step": "send_rfq_emails",
                "error": str(e),
            }
