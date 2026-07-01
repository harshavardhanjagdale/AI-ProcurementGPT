"""
Email Service - Orchestrates email sending/receiving and links to RFQ records.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.email.email_parser import parse_supplier_reply, is_quotation_reply
from app.email.imap_client import imap_client
from app.email.smtp_client import smtp_client
from app.email.template_renderer import render_rfq_email, render_negotiation_email, render_purchase_order_email
from app.models.email import Email
from app.models.email_attachment import EmailAttachment
from app.models.rfq_supplier import RFQSupplier
from app.repositories.rfq_repository import RFQRepository
from app.repositories.supplier_repository import SupplierRepository

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rfq_repo = RFQRepository(db)
        self.supplier_repo = SupplierRepository(db)

    async def send_rfq_emails(
        self,
        rfq_id: str,
        supplier_ids: list[str],
        sender_name: str,
    ) -> list[dict]:
        """Send RFQ request emails to selected suppliers."""
        rfq = await self.rfq_repo.get_with_details(rfq_id)
        if rfq is None:
            raise ValueError(f"RFQ {rfq_id} not found")

        suppliers = await self.supplier_repo.get_by_ids(supplier_ids)
        results = []

        items_data = [
            {
                "product_name": item.product_name,
                "specifications": item.specifications,
                "quantity": item.quantity,
                "unit": item.unit,
            }
            for item in rfq.items
        ]

        for supplier in suppliers:
            body_html = render_rfq_email(
                rfq_number=rfq.rfq_number,
                rfq_title=rfq.title,
                supplier_name=supplier.name,
                items=items_data,
                sender_name=sender_name,
                rfq_description=rfq.description,
                budget_min=float(rfq.budget_min) if rfq.budget_min else None,
                budget_max=float(rfq.budget_max) if rfq.budget_max else None,
                currency=rfq.currency,
                delivery_deadline=str(rfq.delivery_deadline) if rfq.delivery_deadline else None,
            )

            send_result = await smtp_client.send_rfq_email(
                to=supplier.email,
                rfq_number=rfq.rfq_number,
                subject_suffix=rfq.title,
                body_html=body_html,
            )

            email_record = Email(
                rfq_id=rfq_id,
                supplier_id=supplier.id,
                direction="outbound",
                email_type="rfq_request",
                subject=f"{rfq.rfq_number} - {rfq.title}",
                body=body_html,
                from_address=smtp_client.username,
                to_address=supplier.email,
                message_id=send_result.get("message_id"),
                status="sent" if send_result["success"] else "failed",
                sent_at=datetime.now(timezone.utc) if send_result["success"] else None,
            )
            self.db.add(email_record)

            # Update RFQ-supplier status
            from sqlalchemy import update
            await self.db.execute(
                update(RFQSupplier)
                .where(RFQSupplier.rfq_id == rfq_id, RFQSupplier.supplier_id == supplier.id)
                .values(status="email_sent", sent_at=datetime.now(timezone.utc))
            )

            results.append({
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "email": supplier.email,
                "success": send_result["success"],
                "error": send_result.get("error"),
            })

        await self.db.flush()

        # Update RFQ status
        await self.rfq_repo.update_by_id(rfq_id, {"status": "rfq_sent"})

        logger.info(f"Sent RFQ emails for {rfq.rfq_number} to {len(suppliers)} suppliers")
        return results

    async def check_inbox_for_replies(self) -> list[dict]:
        """
        Poll IMAP inbox for new supplier replies.
        Parses emails, saves records, and links to RFQs.
        """
        raw_emails = imap_client.read_unread_emails()
        processed = []

        for raw_email in raw_emails:
            parsed = parse_supplier_reply(raw_email)

            if not parsed["is_quotation"]:
                logger.debug(f"Skipping non-quotation email: {parsed['subject']}")
                continue

            rfq_number = parsed["rfq_number"]
            if rfq_number is None:
                logger.warning(f"Could not extract RFQ number from: {parsed['subject']}")
                continue

            rfq = await self.rfq_repo.get_by_rfq_number(rfq_number)
            if rfq is None:
                logger.warning(f"RFQ not found for number: {rfq_number}")
                continue

            # Find supplier by email
            from sqlalchemy import select
            from app.models.supplier import Supplier
            result = await self.db.execute(
                select(Supplier).where(Supplier.email == parsed["supplier_email"])
            )
            supplier = result.scalar_one_or_none()

            email_record = Email(
                rfq_id=rfq.id,
                supplier_id=supplier.id if supplier else None,
                direction="inbound",
                email_type="supplier_reply",
                subject=parsed["subject"],
                body=parsed["body"],
                from_address=parsed["supplier_email"],
                to_address=smtp_client.username,
                message_id=parsed["message_id"],
                status="received",
                received_at=datetime.now(timezone.utc),
            )
            self.db.add(email_record)
            await self.db.flush()

            for att in parsed["attachments"]:
                attachment_record = EmailAttachment(
                    email_id=email_record.id,
                    file_name=att["file_name"],
                    file_path=att["file_path"],
                    file_type=att["file_type"],
                    file_size_bytes=att.get("file_size_bytes"),
                    ocr_processed=False,
                )
                self.db.add(attachment_record)

            # Update RFQ-supplier status to replied
            if supplier:
                await self.db.execute(
                    update(RFQSupplier)
                    .where(RFQSupplier.rfq_id == rfq.id, RFQSupplier.supplier_id == supplier.id)
                    .values(status="replied", replied_at=datetime.now(timezone.utc))
                )

            await self.db.flush()

            processed.append({
                "rfq_number": rfq_number,
                "rfq_id": rfq.id,
                "supplier_email": parsed["supplier_email"],
                "supplier_id": supplier.id if supplier else None,
                "email_id": email_record.id,
                "attachments_count": len(parsed["attachments"]),
            })

        logger.info(f"Processed {len(processed)} supplier replies from inbox")
        return processed

    async def send_negotiation_email(
        self,
        rfq_id: str,
        supplier_id: str,
        round_number: int,
        original_price: float,
        target_price: float,
        negotiation_message: str,
        sender_name: str,
    ) -> dict:
        """Send a negotiation email to a supplier."""
        rfq = await self.rfq_repo.get_by_id(rfq_id)
        supplier = await self.supplier_repo.get_by_id(supplier_id)

        if not rfq or not supplier:
            raise ValueError("RFQ or Supplier not found")

        body_html = render_negotiation_email(
            rfq_number=rfq.rfq_number,
            supplier_name=supplier.name,
            round_number=round_number,
            original_price=original_price,
            target_price=target_price,
            currency=rfq.currency,
            negotiation_message=negotiation_message,
            sender_name=sender_name,
        )

        send_result = await smtp_client.send_rfq_email(
            to=supplier.email,
            rfq_number=rfq.rfq_number,
            subject_suffix=f"Negotiation Round {round_number}",
            body_html=body_html,
        )

        email_record = Email(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            direction="outbound",
            email_type="negotiation",
            subject=f"{rfq.rfq_number} - Negotiation Round {round_number}",
            body=body_html,
            from_address=smtp_client.username,
            to_address=supplier.email,
            message_id=send_result.get("message_id"),
            status="sent" if send_result["success"] else "failed",
            sent_at=datetime.now(timezone.utc) if send_result["success"] else None,
        )
        self.db.add(email_record)
        await self.db.flush()

        return {
            "success": send_result["success"],
            "email_id": email_record.id,
            "error": send_result.get("error"),
        }

    async def send_purchase_order_email(
        self,
        rfq_id: str,
        supplier_id: str,
        po_number: str,
        items: list[dict],
        total_amount: float,
        currency: str,
        payment_terms: str,
        delivery_date: str,
        sender_name: str,
        pdf_path: str | None = None,
        shipping_address: str | None = None,
    ) -> dict:
        """Send purchase order email with PDF attachment."""
        rfq = await self.rfq_repo.get_by_id(rfq_id)
        supplier = await self.supplier_repo.get_by_id(supplier_id)

        if not rfq or not supplier:
            raise ValueError("RFQ or Supplier not found")

        body_html = render_purchase_order_email(
            po_number=po_number,
            rfq_number=rfq.rfq_number,
            supplier_name=supplier.name,
            items=items,
            total_amount=total_amount,
            currency=currency,
            payment_terms=payment_terms,
            delivery_date=delivery_date,
            sender_name=sender_name,
            shipping_address=shipping_address,
        )

        attachments = []
        if pdf_path:
            attachments.append({"path": pdf_path, "filename": f"{po_number}.pdf"})

        send_result = await smtp_client.send_email(
            to=supplier.email,
            subject=f"{po_number} - Purchase Order",
            body_html=body_html,
            attachments=attachments,
        )

        email_record = Email(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            direction="outbound",
            email_type="po_delivery",
            subject=f"{po_number} - Purchase Order",
            body=body_html,
            from_address=smtp_client.username,
            to_address=supplier.email,
            message_id=send_result.get("message_id"),
            status="sent" if send_result["success"] else "failed",
            sent_at=datetime.now(timezone.utc) if send_result["success"] else None,
        )
        self.db.add(email_record)
        await self.db.flush()

        return {
            "success": send_result["success"],
            "email_id": email_record.id,
            "error": send_result.get("error"),
        }

    async def get_rfq_emails(self, rfq_id: str) -> list[Email]:
        """Get all emails associated with an RFQ."""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Email)
            .where(Email.rfq_id == rfq_id)
            .order_by(Email.created_at.desc())
        )
        return list(result.scalars().all())
