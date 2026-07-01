"""
OCR Processing Node - Processes PDF attachments from supplier replies.
Runs the OCR pipeline on all unprocessed attachments for the RFQ.
"""
import logging

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)


async def process_attachments(state: ProcurementState) -> dict:
    """Process all unprocessed PDF/image attachments through OCR pipeline."""
    rfq_id = state.get("rfq_id")

    if not rfq_id:
        return {
            "ocr_results": [],
            "current_step": "process_attachments",
            "error": "No RFQ ID",
        }

    async with AsyncSessionLocal() as session:
        try:
            service = OCRService(session)
            result = await service.process_rfq_attachments(rfq_id)
            await session.commit()

            logger.info(
                f"OCR complete for RFQ {rfq_id}: "
                f"{result['successful']} success, {result['failed']} failed"
            )

            return {
                "ocr_results": result["results"],
                "current_step": "process_attachments",
            }
        except Exception as e:
            await session.rollback()
            logger.error(f"OCR processing failed: {e}")
            return {
                "ocr_results": [],
                "current_step": "process_attachments",
                "error": str(e),
            }
