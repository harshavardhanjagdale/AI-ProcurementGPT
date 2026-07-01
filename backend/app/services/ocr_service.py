"""
OCR Service - High-level orchestration for document processing.
Coordinates between email attachments, OCR pipeline, and quotation creation.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ocr.pipeline import ocr_pipeline
from app.services.quotation_service import QuotationService

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quotation_service = QuotationService(db)

    async def process_rfq_attachments(self, rfq_id: str) -> dict:
        """
        Process all unprocessed PDF/image attachments for an RFQ.
        Creates quotation records from successfully extracted data.
        """
        results = await self.quotation_service.process_all_pending_attachments(rfq_id)

        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        logger.info(
            f"OCR processing complete for RFQ {rfq_id}: "
            f"{len(successful)} success, {len(failed)} failed"
        )

        return {
            "rfq_id": rfq_id,
            "total_processed": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }

    async def process_single_file(self, file_path: str, file_type: str) -> dict:
        """
        Process a single file through OCR (standalone, not linked to email).
        Useful for manual uploads or testing.
        """
        return await ocr_pipeline.process_attachment(file_path, file_type)

    async def reprocess_attachment(self, attachment_id: str) -> dict:
        """Reprocess a specific attachment (e.g., after OCR fix)."""
        from sqlalchemy import update
        from app.models.email_attachment import EmailAttachment

        await self.db.execute(
            update(EmailAttachment)
            .where(EmailAttachment.id == attachment_id)
            .values(ocr_processed=False, ocr_result_json=None)
        )
        await self.db.flush()

        return await self.quotation_service.process_attachment(attachment_id)
