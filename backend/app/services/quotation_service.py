"""
Quotation Service - Processes supplier quotations from OCR, stores them,
and provides comparison capabilities.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.email_attachment import EmailAttachment
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.ocr.pipeline import ocr_pipeline
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.rfq_repository import RFQRepository
from app.repositories.supplier_repository import SupplierRepository

logger = logging.getLogger(__name__)


class QuotationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quotation_repo = QuotationRepository(db)
        self.rfq_repo = RFQRepository(db)
        self.supplier_repo = SupplierRepository(db)

    async def process_attachment(self, attachment_id: str) -> dict:
        """
        Process a single email attachment through OCR pipeline.
        Creates a quotation record from extracted data.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.email import Email

        result = await self.db.execute(
            select(EmailAttachment).where(EmailAttachment.id == attachment_id)
        )
        attachment = result.scalar_one_or_none()
        if not attachment:
            raise NotFoundError("EmailAttachment", attachment_id)

        # Run OCR pipeline
        ocr_result = await ocr_pipeline.process_attachment(
            file_path=attachment.file_path,
            file_type=attachment.file_type,
        )

        # Update attachment record
        from sqlalchemy import update
        await self.db.execute(
            update(EmailAttachment)
            .where(EmailAttachment.id == attachment_id)
            .values(
                ocr_processed=True,
                ocr_result_json=ocr_result.get("extracted_data"),
            )
        )

        if not ocr_result.get("success") or ocr_result.get("extraction_failed"):
            await self.db.flush()
            return {
                "success": False,
                "attachment_id": attachment_id,
                "error": ocr_result.get("error", "Extraction failed"),
                "raw_text": ocr_result.get("raw_text", ""),
            }

        # Get email to link RFQ and supplier
        result = await self.db.execute(
            select(Email).where(Email.id == attachment.email_id)
        )
        email_record = result.scalar_one_or_none()

        if email_record and email_record.rfq_id and email_record.supplier_id:
            extracted = ocr_result["extracted_data"]
            quotation = await self._create_quotation_from_extraction(
                rfq_id=email_record.rfq_id,
                supplier_id=email_record.supplier_id,
                email_id=email_record.id,
                extracted_data=extracted,
                raw_text=ocr_result.get("raw_text", ""),
            )
            await self.db.flush()
            return {
                "success": True,
                "attachment_id": attachment_id,
                "quotation_id": quotation.id,
                "extracted_data": extracted,
                "confidence": ocr_result.get("confidence", 0),
            }

        await self.db.flush()
        return {
            "success": True,
            "attachment_id": attachment_id,
            "quotation_id": None,
            "extracted_data": ocr_result["extracted_data"],
            "note": "Could not link to RFQ/supplier - quotation not created",
        }

    async def _create_quotation_from_extraction(
        self,
        rfq_id: str,
        supplier_id: str,
        email_id: str,
        extracted_data: dict,
        raw_text: str,
    ) -> Quotation:
        """Create a Quotation record from extracted OCR data.

        Each processed attachment yields a new quotation row. A supplier's revised quote
        (received after a negotiation round) is stored as a NEW row with an incremented
        negotiation_round, rather than being skipped — so both the original and the revised
        quote are preserved and can be shown side by side. Duplicate processing of the same
        attachment is already prevented upstream by the attachment's ocr_processed flag.
        """
        prior = await self.quotation_repo.get_all_by_rfq_and_supplier(rfq_id, supplier_id)

        # Only count quotations from distinct emails for negotiation_round.
        # If a quotation already exists from this exact email, it's a duplicate
        # (e.g. multiple attachments in the same email, or race condition).
        existing_for_email = [q for q in prior if q.email_id == email_id]
        if existing_for_email:
            logger.warning(
                f"Quotation already exists for email {email_id} + supplier {supplier_id} — returning existing"
            )
            return existing_for_email[0]

        seen_emails = {q.email_id for q in prior if q.email_id}
        negotiation_round = len(seen_emails)  # 0 = first email, 1 = second email, …
        if negotiation_round:
            logger.info(
                f"Revised quote (round {negotiation_round}) for RFQ {rfq_id} + supplier {supplier_id}"
            )

        raw_tax_pct = extracted_data.get("tax_percent")
        raw_tax_amt = extracted_data.get("tax_amount")
        raw_subtotal = extracted_data.get("subtotal")
        raw_total = extracted_data.get("total_amount", 0)

        quotation = Quotation(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            email_id=email_id,
            total_amount=raw_subtotal or raw_total,
            tax_percent=raw_tax_pct,
            tax_amount=raw_tax_amt,
            grand_total=raw_total if raw_tax_amt else None,
            currency=extracted_data.get("currency", "USD"),
            delivery_days=extracted_data.get("delivery_days"),
            warranty_terms=extracted_data.get("warranty_terms"),
            payment_terms=extracted_data.get("payment_terms"),
            validity_days=extracted_data.get("validity_days", 30),
            status="received",
            raw_ocr_text=raw_text,
            negotiation_round=negotiation_round,
        )
        quotation = await self.quotation_repo.create(quotation)

        items = extracted_data.get("items", [])
        for item_data in items:
            q_item = QuotationItem(
                quotation_id=quotation.id,
                product_name=item_data.get("product_name", "Unknown"),
                unit_price=item_data.get("unit_price", 0),
                quantity=item_data.get("quantity", 1),
                total_price=item_data.get("total_price", 0),
                specifications=item_data.get("specifications"),
            )
            self.db.add(q_item)

        await self.db.flush()
        logger.info(f"Created quotation {quotation.id} with {len(items)} items")
        return quotation

    async def process_all_pending_attachments(self, rfq_id: str) -> list[dict]:
        """Process all unprocessed attachments for a given RFQ."""
        from sqlalchemy import select
        from app.models.email import Email

        result = await self.db.execute(
            select(EmailAttachment)
            .join(Email, Email.id == EmailAttachment.email_id)
            .where(
                Email.rfq_id == rfq_id,
                EmailAttachment.ocr_processed == False,
                EmailAttachment.file_type.in_(["pdf", "jpg", "jpeg", "png"]),
            )
        )
        attachments = list(result.scalars().all())

        results = []
        for att in attachments:
            result = await self.process_attachment(att.id)
            results.append(result)

        return results

    async def get_quotation(self, quotation_id: str) -> Quotation:
        quotation = await self.quotation_repo.get_with_items(quotation_id)
        if quotation is None:
            raise NotFoundError("Quotation", quotation_id)
        return quotation

    async def get_rfq_quotations(self, rfq_id: str) -> list[Quotation]:
        return await self.quotation_repo.get_by_rfq(rfq_id)

    async def get_comparison(self, rfq_id: str) -> dict:
        """Get side-by-side comparison of all quotations for an RFQ."""
        quotations = await self.quotation_repo.get_by_rfq(rfq_id)
        rfq = await self.rfq_repo.get_with_details(rfq_id)

        if not quotations:
            return {"rfq_id": rfq_id, "quotations": [], "comparison": None}

        comparison_data = []
        for q in quotations:
            supplier = await self.supplier_repo.get_by_id(q.supplier_id)
            comparison_data.append({
                "quotation_id": q.id,
                "supplier_id": q.supplier_id,
                "supplier_name": supplier.name if supplier else "Unknown",
                "total_amount": float(q.total_amount),
                "currency": q.currency,
                "delivery_days": q.delivery_days,
                "warranty_terms": q.warranty_terms,
                "payment_terms": q.payment_terms,
                "ai_score": float(q.ai_score) if q.ai_score else None,
                "ai_ranking": q.ai_ranking,
                "status": q.status,
                "items": [
                    {
                        "product_name": item.product_name,
                        "unit_price": float(item.unit_price),
                        "quantity": item.quantity,
                        "total_price": float(item.total_price),
                    }
                    for item in q.items
                ],
            })

        # Sort by AI score (descending) or by price (ascending) if no scores
        if any(d["ai_score"] for d in comparison_data):
            comparison_data.sort(key=lambda x: x["ai_score"] or 0, reverse=True)
        else:
            comparison_data.sort(key=lambda x: x["total_amount"])

        return {
            "rfq_id": rfq_id,
            "rfq_number": rfq.rfq_number if rfq else None,
            "total_quotations": len(comparison_data),
            "quotations": comparison_data,
            "lowest_price": min(d["total_amount"] for d in comparison_data) if comparison_data else 0,
            "highest_price": max(d["total_amount"] for d in comparison_data) if comparison_data else 0,
        }

    async def accept_quotation(self, quotation_id: str) -> Quotation:
        """Mark a quotation as accepted."""
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if not quotation:
            raise NotFoundError("Quotation", quotation_id)

        await self.quotation_repo.update_by_id(quotation_id, {"status": "accepted"})

        # Reject all other quotations for this RFQ
        other_quotations = await self.quotation_repo.get_by_rfq(quotation.rfq_id)
        for q in other_quotations:
            if q.id != quotation_id and q.status not in ("rejected", "expired"):
                await self.quotation_repo.update_by_id(q.id, {"status": "rejected"})

        await self.db.flush()
        return await self.quotation_repo.get_with_items(quotation_id)

    async def reject_quotation(self, quotation_id: str) -> Quotation:
        """Mark a quotation as rejected."""
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if not quotation:
            raise NotFoundError("Quotation", quotation_id)

        await self.quotation_repo.update_by_id(quotation_id, {"status": "rejected"})
        return await self.quotation_repo.get_with_items(quotation_id)
