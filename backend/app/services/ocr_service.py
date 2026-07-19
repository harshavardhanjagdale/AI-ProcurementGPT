"""
OCR Service - High-level orchestration for document processing.
Coordinates between email attachments, OCR pipeline, and quotation creation.
"""
import logging
import traceback

from sqlalchemy.ext.asyncio import AsyncSession

from app.ocr.pipeline import ocr_pipeline
from app.services.quotation_service import QuotationService
from app.ocr.logger import (
    log_attachment_start, log_attachment_success, log_attachment_error,
    log_extraction_result, log_quotation_data, ocr_logger
)

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quotation_service = QuotationService(db)

    async def process_rfq_attachments(self, rfq_id: str, *, skip_content_validation: bool = False) -> dict:
        """
        Process all unprocessed PDF/image attachments for an RFQ.
        Creates quotation records from successfully extracted data.
        """
        try:
            logger.info(f"[OCR-SERVICE] Starting to process attachments for RFQ {rfq_id} (skip_content_validation={skip_content_validation})")
            ocr_logger.info(f"[RFQ] Processing started for {rfq_id}")

            results = await self.quotation_service.process_all_pending_attachments(rfq_id, skip_content_validation=skip_content_validation)

            successful = [r for r in results if r.get("success")]
            failed = [r for r in results if not r.get("success")]

            logger.info(
                f"[OCR-SERVICE] Processing complete for RFQ {rfq_id}: "
                f"{len(successful)} success, {len(failed)} failed"
            )
            
            ocr_logger.info(f"[RESULTS] Success: {len(successful)}, Failed: {len(failed)}")
            
            if failed:
                for failed_result in failed:
                    logger.warning(f"[OCR-SERVICE] Failed attachment: {failed_result}")
                    ocr_logger.warning(f"[FAILED] {failed_result}")

            return {
                "rfq_id": rfq_id,
                "total_processed": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "results": results,
            }
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[OCR-SERVICE] ERROR processing RFQ {rfq_id}: {error_msg}")
            logger.error(f"[OCR-SERVICE] Traceback:\n{traceback.format_exc()}")
            
            ocr_logger.error(f"[FATAL ERROR] {error_msg}")
            ocr_logger.error(f"[TRACE]\n{traceback.format_exc()}")
            raise

    async def process_single_file(self, file_path: str, file_type: str) -> dict:
        """
        Process a single file through OCR (standalone, not linked to email).
        Useful for manual uploads or testing.
        """
        try:
            logger.info(f"[OCR-SERVICE] Processing single file: {file_path}")
            ocr_logger.info(f"[FILE] Processing: {file_path}")
            
            result = await ocr_pipeline.process_attachment(file_path, file_type)
            
            ocr_logger.info(f"[FILE SUCCESS] {file_path}")
            return result
        except Exception as e:
            logger.error(f"[OCR-SERVICE] ERROR processing file {file_path}: {e}")
            logger.error(f"[OCR-SERVICE] Traceback:\n{traceback.format_exc()}")
            
            ocr_logger.error(f"[FILE ERROR] {file_path}: {e}")
            ocr_logger.error(f"[TRACE]\n{traceback.format_exc()}")
            raise

    async def reprocess_attachment(self, attachment_id: str) -> dict:
        """Reprocess a specific attachment (e.g., after OCR fix)."""
        from sqlalchemy import update
        from app.models.email_attachment import EmailAttachment

        try:
            logger.info(f"[OCR-SERVICE] Reprocessing attachment {attachment_id}")
            ocr_logger.info(f"[REPROCESS] Attachment: {attachment_id}")
            
            await self.db.execute(
                update(EmailAttachment)
                .where(EmailAttachment.id == attachment_id)
                .values(ocr_processed=False, ocr_result_json=None)
            )
            await self.db.flush()

            result = await self.quotation_service.process_attachment(attachment_id)
            logger.info(f"[OCR-SERVICE] Reprocess complete for {attachment_id}")
            
            ocr_logger.info(f"[REPROCESS SUCCESS] {attachment_id}")
            return result
        except Exception as e:
            logger.error(f"[OCR-SERVICE] ERROR reprocessing {attachment_id}: {e}")
            logger.error(f"[OCR-SERVICE] Traceback:\n{traceback.format_exc()}")
            
            ocr_logger.error(f"[REPROCESS ERROR] {attachment_id}: {e}")
            ocr_logger.error(f"[TRACE]\n{traceback.format_exc()}")
            raise
