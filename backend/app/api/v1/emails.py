from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_admin
from app.database.session import get_db
from app.services.email_service import EmailService

router = APIRouter()


@router.get("")
async def list_emails(
    rfq_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List all emails, optionally filtered by RFQ."""
    service = EmailService(db)
    if rfq_id:
        emails = await service.get_rfq_emails(rfq_id)
    else:
        from sqlalchemy import select
        from app.models.email import Email
        result = await db.execute(
            select(Email).order_by(Email.created_at.desc()).limit(50)
        )
        emails = list(result.scalars().all())

    return {
        "items": [
            {
                "id": e.id,
                "rfq_id": e.rfq_id,
                "supplier_id": e.supplier_id,
                "direction": e.direction,
                "email_type": e.email_type,
                "subject": e.subject,
                "from_address": e.from_address,
                "to_address": e.to_address,
                "status": e.status,
                "sent_at": e.sent_at.isoformat() if e.sent_at else None,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in emails
        ],
        "total": len(emails),
    }


@router.get("/{email_id}")
async def get_email_detail(
    email_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get email detail with attachments."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.email import Email

    result = await db.execute(
        select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id)
    )
    email = result.scalar_one_or_none()
    if email is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Email", email_id)

    return {
        "id": email.id,
        "rfq_id": email.rfq_id,
        "supplier_id": email.supplier_id,
        "direction": email.direction,
        "email_type": email.email_type,
        "subject": email.subject,
        "body": email.body,
        "from_address": email.from_address,
        "to_address": email.to_address,
        "status": email.status,
        "message_id": email.message_id,
        "sent_at": email.sent_at.isoformat() if email.sent_at else None,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "created_at": email.created_at.isoformat(),
        "attachments": [
            {
                "id": att.id,
                "file_name": att.file_name,
                "file_type": att.file_type,
                "file_size_bytes": att.file_size_bytes,
                "ocr_processed": att.ocr_processed,
            }
            for att in email.attachments
        ],
    }


@router.post("/send-rfq/{rfq_id}")
async def send_rfq_emails(
    rfq_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manually trigger sending RFQ emails to all selected suppliers."""
    from app.models.rfq_supplier import RFQSupplier
    from sqlalchemy import select

    result = await db.execute(
        select(RFQSupplier.supplier_id).where(RFQSupplier.rfq_id == rfq_id)
    )
    supplier_ids = [row[0] for row in result.all()]

    if not supplier_ids:
        return {"error": "No suppliers selected for this RFQ"}

    service = EmailService(db)
    results = await service.send_rfq_emails(
        rfq_id=rfq_id,
        supplier_ids=supplier_ids,
        sender_name=current_user.full_name,
    )
    return {"results": results, "total_sent": sum(1 for r in results if r["success"])}


@router.post("/check-inbox")
async def check_inbox(
    _current_user=Depends(get_admin),
):
    """Manually trigger inbox check for supplier replies."""
    from app.email.background_worker import email_worker
    results = await email_worker.poll_once()
    return {
        "processed": len(results),
        "replies": results,
    }
