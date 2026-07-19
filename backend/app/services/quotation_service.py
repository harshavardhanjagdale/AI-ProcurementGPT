"""
Quotation Service - Processes supplier quotations from OCR, stores them,
and provides comparison capabilities.

Includes pre-OCR sender verification and post-OCR content validation
(supplier name match + item relevance) before accepting a quotation.
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


class QuotationValidationError(Exception):
    """Raised when a quotation fails pre/post-OCR validation checks."""
    def __init__(self, reason: str, details: str):
        self.reason = reason
        self.details = details
        super().__init__(f"{reason}: {details}")


class QuotationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quotation_repo = QuotationRepository(db)
        self.rfq_repo = RFQRepository(db)
        self.supplier_repo = SupplierRepository(db)

    async def process_attachment(self, attachment_id: str, *, skip_content_validation: bool = False) -> dict:
        """
        Process a single email attachment through OCR pipeline with pre/post hooks.

        Hook architecture:
        1. PRE-OCR HOOK (validate_sender) — verifies the email sender is a known
           supplier who was invited for this RFQ
        2. OCR EXECUTION — runs Tesseract + LLM extraction
        3. POST-OCR HOOK (validate_quotation_content) — verifies the extracted
           quotation is from the right supplier and quotes relevant items

        When skip_content_validation is True (e.g. supplier offered an alternative
        product), the post-OCR content check is bypassed so that a quotation for
        a different product/brand than the original RFQ is still accepted.
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

        # Get email to know sender and RFQ context
        result = await self.db.execute(
            select(Email).where(Email.id == attachment.email_id)
        )
        email_record = result.scalar_one_or_none()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PRE-OCR HOOK: Sender verification
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if email_record and email_record.rfq_id and email_record.from_address:
            sender_check = await self._pre_ocr_hook(
                rfq_id=email_record.rfq_id,
                sender_email=email_record.from_address,
            )
            if not sender_check["valid"]:
                logger.warning(f"[PRE-OCR-HOOK] REJECTED: {sender_check['reason']}")
                from sqlalchemy import update as sql_update
                await self.db.execute(
                    sql_update(EmailAttachment)
                    .where(EmailAttachment.id == attachment_id)
                    .values(ocr_processed=True)
                )
                await self.db.flush()
                raise QuotationValidationError(
                    reason="sender_verification_failed",
                    details=sender_check["reason"],
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # OCR EXECUTION — pass RFQ items as context so the LLM can
        # cross-reference quantities when OCR drops table columns.
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        rfq_items_context = None
        if email_record and email_record.rfq_id:
            rfq = await self.rfq_repo.get_with_details(email_record.rfq_id)
            if rfq and rfq.items:
                rfq_items_context = [
                    {"product_name": item.product_name, "quantity": item.quantity}
                    for item in rfq.items
                ]

        ocr_result = await ocr_pipeline.process_attachment(
            file_path=attachment.file_path,
            file_type=attachment.file_type,
            rfq_items=rfq_items_context,
        )

        from sqlalchemy import update as sql_update
        await self.db.execute(
            sql_update(EmailAttachment)
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
                "error": ocr_result.get("error", "Could not extract data from document"),
                "raw_text": ocr_result.get("raw_text", ""),
            }

        extracted = ocr_result["extracted_data"]

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # POST-OCR HOOK: Content verification (supplier name + item category)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if skip_content_validation:
            logger.info("[POST-OCR-HOOK] SKIPPED — alternative product offer, bypassing content validation")
        elif email_record and email_record.rfq_id and email_record.supplier_id:
            post_check = await self._post_ocr_hook(
                rfq_id=email_record.rfq_id,
                supplier_id=email_record.supplier_id,
                extracted_data=extracted,
            )
            if not post_check["valid"]:
                logger.warning(f"[POST-OCR-HOOK] REJECTED: {post_check['details']}")
                await self.db.flush()
                raise QuotationValidationError(
                    reason="content_validation_failed",
                    details=post_check["details"],
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # CREATE QUOTATION (all hooks passed)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if email_record and email_record.rfq_id and email_record.supplier_id:
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
            "extracted_data": extracted,
            "note": "Could not link to RFQ/supplier - quotation not created",
        }

    async def _pre_ocr_hook(self, rfq_id: str, sender_email: str) -> dict:
        """
        PRE-OCR HOOK: Validates that the email sender is an invited supplier for this RFQ.
        Called BEFORE running expensive OCR processing.
        """
        return await self.validate_sender(rfq_id=rfq_id, sender_email=sender_email)

    async def _post_ocr_hook(self, rfq_id: str, supplier_id: str, extracted_data: dict) -> dict:
        """
        POST-OCR HOOK: Validates extracted content — checks supplier name match
        and whether quoted items are in the same product category as the RFQ.
        Called AFTER OCR extraction but BEFORE creating the quotation record.

        Only rejects if:
        - Supplier name is completely different (not just abbreviated/trade name)
        - Items are in a completely different product category
        """
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        expected_name = supplier.name if supplier else "Unknown"
        return await self.validate_quotation_content(
            rfq_id=rfq_id,
            supplier_name=expected_name,
            extracted_data=extracted_data,
        )

    async def validate_sender(self, rfq_id: str, sender_email: str) -> dict:
        """
        Pre-OCR check: verify the sender email belongs to a supplier
        we actually sent this RFQ to.

        Returns: {"valid": bool, "supplier_id": str|None, "supplier_name": str|None, "reason": str|None}
        """
        from sqlalchemy import select
        from app.models.supplier import Supplier
        from app.models.rfq_supplier import RFQSupplier

        # Find supplier by email
        result = await self.db.execute(
            select(Supplier).where(Supplier.email == sender_email)
        )
        supplier = result.scalar_one_or_none()

        if not supplier:
            return {
                "valid": False,
                "supplier_id": None,
                "supplier_name": None,
                "reason": f"Unknown sender '{sender_email}' — not in our supplier database.",
            }

        # Check if this supplier was actually invited for this RFQ
        result = await self.db.execute(
            select(RFQSupplier).where(
                RFQSupplier.rfq_id == rfq_id,
                RFQSupplier.supplier_id == supplier.id,
                RFQSupplier.status.in_(["email_sent", "replied"]),
            )
        )
        rfq_supplier = result.scalar_one_or_none()

        if not rfq_supplier:
            return {
                "valid": False,
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "reason": (
                    f"Supplier '{supplier.name}' ({sender_email}) replied, "
                    f"but we never sent them this RFQ. Possible mismatch."
                ),
            }

        return {
            "valid": True,
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "reason": None,
        }

    async def validate_quotation_content(
        self, rfq_id: str, supplier_name: str, extracted_data: dict
    ) -> dict:
        """
        Post-OCR check: use LLM to verify:
        1. The supplier name in the quotation header matches who we expect
        2. The quoted items are relevant to what we requested

        Returns: {"valid": bool, "issues": list[str], "details": str}
        """
        from app.ai.llm_client import llm_client

        rfq = await self.rfq_repo.get_with_details(rfq_id)
        if not rfq:
            return {"valid": False, "issues": ["rfq_not_found"], "details": "RFQ not found."}

        # Build RFQ context
        rfq_items = [
            f"- {item.product_name} (qty: {item.quantity})"
            for item in rfq.items
        ]
        rfq_items_text = "\n".join(rfq_items) if rfq_items else "No items specified"

        # Build extracted quotation context
        extracted_supplier = extracted_data.get("supplier_name", "Unknown")
        extracted_items = extracted_data.get("items", [])
        extracted_items_text = "\n".join(
            f"- {it.get('product_name', 'Unknown')} (qty: {it.get('quantity', '?')})"
            for it in extracted_items
        ) if extracted_items else "No items found"

        validation_prompt = f"""You are a procurement validation agent. Check if this received quotation is meant for the given RFQ.

EXPECTED SUPPLIER: {supplier_name}
QUOTATION HEADER SUPPLIER NAME: {extracted_supplier}

RFQ REQUESTED ITEMS:
{rfq_items_text}

QUOTATION ITEMS RECEIVED:
{extracted_items_text}

Check ONLY these two things:

1. SUPPLIER MATCH: Does the quotation come from the expected supplier?
   - PASS if the names are similar, abbreviated, or use trade names
   - FAIL ONLY if clearly a completely different company

2. ITEM CATEGORY MATCH: Are the quoted items in the same PRODUCT CATEGORY as requested?
   - PASS if the product categories match (e.g. "laptops" → "Business Laptop" = PASS)
   - PASS if supplier quoted specific brands/models/specs for a requested category
   - PASS even if quantities, prices, or specs differ from the RFQ
   - FAIL ONLY if the product category is completely unrelated (e.g. requested "laptops" → quoted "office desks")

IMPORTANT: Do NOT check quantities, prices, specifications, or any other details. You are ONLY checking whether the quotation is from the right supplier and quotes the right type of products. Quantity differences, missing items, or extra items are perfectly acceptable.

Return JSON:
{{"supplier_match": true/false, "supplier_match_reason": "brief reason", "items_relevant": true/false, "items_relevance_reason": "brief reason"}}"""

        try:
            result = await llm_client.generate_json(
                system_prompt="You are a validation agent. Return only valid JSON.",
                user_prompt=validation_prompt,
                max_tokens=500,
            )
        except Exception as e:
            logger.warning(f"[VALIDATION] LLM validation call failed: {e} — allowing quotation through")
            return {"valid": True, "issues": [], "details": "Validation skipped (LLM error)"}

        if result is None:
            return {"valid": True, "issues": [], "details": "Validation skipped (no LLM response)"}

        issues = []
        details_parts = []

        if not result.get("supplier_match", True):
            issues.append("supplier_name_mismatch")
            details_parts.append(
                f"Supplier mismatch: expected '{supplier_name}', "
                f"but quotation header says '{extracted_supplier}'. "
                f"Reason: {result.get('supplier_match_reason', 'Unknown')}"
            )

        if not result.get("items_relevant", True):
            issues.append("items_not_relevant")
            details_parts.append(
                f"Item mismatch: {result.get('items_relevance_reason', 'Quoted items do not match the RFQ request.')}"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "details": " | ".join(details_parts) if details_parts else "Validation passed.",
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

    async def process_all_pending_attachments(self, rfq_id: str, *, skip_content_validation: bool = False) -> list[dict]:
        """Process all unprocessed attachments for a given RFQ."""
        from sqlalchemy import select
        from app.models.email import Email

        logger.info(f"[PENDING-ATT] Looking for unprocessed attachments for RFQ {rfq_id}")

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

        logger.info(f"[PENDING-ATT] Found {len(attachments)} unprocessed attachments for RFQ {rfq_id}")
        for att in attachments:
            logger.info(f"[PENDING-ATT]   - id={att.id}, file={att.file_name}, email_id={att.email_id}")

        if not attachments:
            # Also log total attachment count for this RFQ to diagnose
            all_result = await self.db.execute(
                select(EmailAttachment)
                .join(Email, Email.id == EmailAttachment.email_id)
                .where(Email.rfq_id == rfq_id)
            )
            all_atts = list(all_result.scalars().all())
            logger.warning(
                f"[PENDING-ATT] No unprocessed attachments! "
                f"Total attachments for RFQ {rfq_id}: {len(all_atts)} "
                f"(all already ocr_processed={[a.ocr_processed for a in all_atts]})"
            )

        results = []
        for att in attachments:
            try:
                att_result = await self.process_attachment(att.id, skip_content_validation=skip_content_validation)
                results.append(att_result)
            except QuotationValidationError as e:
                logger.warning(f"[VALIDATION] Attachment {att.id} failed validation: {e}")
                results.append({
                    "success": False,
                    "attachment_id": att.id,
                    "error": f"Validation failed: {e.details}",
                    "validation_reason": e.reason,
                    "validation_details": e.details,
                })

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

        # Sort by AI ranking (ascending) or by price (ascending) if no rankings
        if any(d["ai_ranking"] for d in comparison_data):
            comparison_data.sort(key=lambda x: x["ai_ranking"] or float('inf'))
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
