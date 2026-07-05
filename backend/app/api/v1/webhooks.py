"""
Email Webhook Receiver - Listens for incoming emails and triggers workflow resume.
Email services (Mailgun, SendGrid, etc.) can POST to this endpoint when emails arrive.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.email import Email
from app.models.workflow_session import WorkflowSession
from app.models.workflow_step import WorkflowStep
from app.models.workflow_event import WorkflowEvent
from app.models.conversation_message import ConversationMessage
from app.models.base import generate_uuid, ist_now

logger = logging.getLogger(__name__)

router = APIRouter()


class IncomingEmail(BaseModel):
    """Webhook payload from email service."""
    sender: str
    to: str
    subject: str
    timestamp: str | None = None
    body: str | None = None
    attachments: list[dict] | None = None


@router.post("/webhook/email-arrived")
async def webhook_email_arrived(
    email_data: IncomingEmail,
    x_webhook_token: str | None = Header(None),
):
    """
    Webhook endpoint for email services to POST when emails arrive.
    
    Email service should send POST with:
    {
      "sender": "supplier@company.com",
      "to": "your-email@company.com",
      "subject": "Re: RFQ-2026-00050 - Quote",
      "body": "Please find our quotation attached",
      "attachments": [{"filename": "quote.pdf", "url": "..."}]
    }
    
    Authenticates with X-Webhook-Token header (set in .env)
    """
    from app.core.config import settings
    
    # Verify webhook token for security
    if x_webhook_token != settings.WEBHOOK_TOKEN:
        logger.warning(f"Unauthorized webhook call from {email_data.sender}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(f"[WEBHOOK] Email arrived from {email_data.sender}, subject: {email_data.subject}")

    # Get DB session
    from app.database.connection import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            # 1. Find any RFQ this email is replying to
            # Look for RFQ number in subject line (e.g., "RFQ-2026-00050")
            rfq_number = _extract_rfq_number(email_data.subject)
            
            if not rfq_number:
                logger.warning(f"No RFQ number found in subject: {email_data.subject}")
                return {"status": "ignored", "reason": "No RFQ number in subject"}

            # 2. Find the RFQ
            from app.models.rfq import RFQ
            result = await session.execute(
                select(RFQ).where(RFQ.rfq_number == rfq_number)
            )
            rfq = result.scalar_one_or_none()

            if not rfq:
                logger.warning(f"RFQ not found: {rfq_number}")
                return {"status": "ignored", "reason": f"RFQ {rfq_number} not found"}

            # 3. Save the email (same as background worker does)
            email = Email(
                id=generate_uuid(),
                rfq_id=rfq.id,
                direction="inbound",
                email_type="supplier_reply",
                subject=email_data.subject,
                body=email_data.body or "",
                from_address=email_data.sender,
                to_address=email_data.to,
                status="received",
                received_at=datetime.now(timezone.utc),
            )
            session.add(email)
            await session.flush()

            # 4. Handle attachments if provided
            if email_data.attachments:
                from app.models.email_attachment import EmailAttachment
                for att in email_data.attachments:
                    attachment = EmailAttachment(
                        id=generate_uuid(),
                        email_id=email.id,
                        file_name=att.get("filename", "attachment"),
                        file_path=att.get("url", ""),
                        file_type=att.get("content_type", "application/octet-stream"),
                        file_size_bytes=att.get("size"),
                        ocr_processed=False,
                    )
                    session.add(attachment)

            await session.flush()

            # 5. IMMEDIATELY update any waiting workflow sessions
            await _update_waiting_sessions(session, rfq.id)

            # Find the session we just updated, so we can resume it once committed
            result = await session.execute(
                select(WorkflowSession).where(
                    WorkflowSession.rfq_id == rfq.id,
                    WorkflowSession.status == "active"
                )
            )
            ws = result.scalar_one_or_none()
            resume_session_id = ws.id if ws else None
            resume_thread_id = ws.langgraph_thread_id if ws else None

            await session.commit()

            logger.info(f"[WEBHOOK] ✓ Email processed from {email_data.sender} for {rfq_number}")

        except Exception as e:
            await session.rollback()
            logger.error(f"[WEBHOOK] Error processing email: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # 6. RESUME THE WORKFLOW to process the email. This must happen after the
    # commit above so the process_attachments node (which opens its own DB
    # session) can actually see the email/attachment rows just inserted.
    if resume_session_id and resume_thread_id:
        logger.info(f"[WEBHOOK] Resuming workflow for session {resume_session_id}")
        from app.workflows.session_workflow import session_workflow_service
        resume_result = await session_workflow_service.resume_after_reply(resume_session_id, resume_thread_id)
        logger.info(f"[WEBHOOK] Workflow result - current step: {resume_result.get('current_step')}")

    return {
        "status": "processed",
        "rfq_number": rfq_number,
        "rfq_id": rfq.id,
        "message": "Email received and workflow resumed"
    }


async def _update_waiting_sessions(session: AsyncSession, rfq_id: str):
    """Update WorkflowSession status when email arrives."""
    # Find waiting sessions for this RFQ
    result = await session.execute(
        select(WorkflowSession).where(
            WorkflowSession.rfq_id == rfq_id,
            WorkflowSession.status == "waiting",
        )
    )
    waiting_sessions = list(result.scalars().all())

    for ws in waiting_sessions:
        logger.info(f"[WEBHOOK] Updating session {ws.id} - email arrived for {rfq_id}")
        
        ws.current_step = "process_attachments"
        ws.current_agent = "OCR Agent"
        ws.status = "active"
        ws.progress_percentage = 57.0

        # Update steps
        await session.execute(
            update(WorkflowStep).where(
                WorkflowStep.session_id == ws.id,
                WorkflowStep.name == "await_supplier_replies",
            ).values(status="completed", completed_at=ist_now())
        )
        await session.execute(
            update(WorkflowStep).where(
                WorkflowStep.session_id == ws.id,
                WorkflowStep.name == "process_attachments",
            ).values(status="running", started_at=ist_now())
        )

        # Add event
        event = WorkflowEvent(
            id=generate_uuid(),
            session_id=ws.id,
            event_type="email_received",
            title="Supplier Email Received via Webhook",
            description="Immediate webhook notification triggered workflow resume",
            agent="Email Webhook",
        )
        session.add(event)

        # Add chat message
        msg = ConversationMessage(
            id=generate_uuid(),
            session_id=ws.id,
            role="assistant",
            content="⚡ **Instant Alert!** Supplier email received! Processing quotation immediately...",
            message_type="event",
        )
        session.add(msg)


def _extract_rfq_number(subject: str) -> str | None:
    """Extract RFQ number from email subject (e.g., 'RFQ-2026-00050')."""
    import re
    match = re.search(r'RFQ-\d{4}-\d{5}', subject)
    return match.group(0) if match else None
