"""
OCR Processing Node - Processes PDF attachments from supplier replies.
Runs the OCR pipeline on all unprocessed attachments for the RFQ.
"""
import logging
import traceback
import time

from app.agents.state import ProcurementState
from app.database.connection import AsyncSessionLocal
from app.services.ocr_service import OCRService
from app.ocr.logger import (
    log_ocr_start, log_ocr_complete, log_ocr_failure, 
    generate_ocr_report
)

logger = logging.getLogger(__name__)


async def process_attachments(state: ProcurementState) -> dict:
    """Process all unprocessed PDF/image attachments through OCR pipeline."""
    rfq_id = state.get("rfq_id")
    start_time = time.time()
    
    log_ocr_start(rfq_id, 0)  # Will update with actual count

    if not rfq_id:
        error_msg = "No RFQ ID found in state"
        logger.error(f"[OCR] ERROR: {error_msg}")
        return {
            "ocr_results": [],
            "current_step": "process_attachments",
            "error": error_msg,
        }

    async with AsyncSessionLocal() as session:
        try:
            logger.info(f"[OCR] Initializing OCR service for RFQ {rfq_id}")
            service = OCRService(session)
            
            logger.info(f"[OCR] Processing attachments for RFQ {rfq_id}")
            result = await service.process_rfq_attachments(rfq_id)
            await session.commit()
            
            total_time = time.time() - start_time

            logger.info(
                f"[OCR] SUCCESS for RFQ {rfq_id}: "
                f"{result['successful']} success, {result['failed']} failed in {total_time:.2f}s"
            )
            
            # Log completion
            log_ocr_complete(rfq_id, result['successful'], result['failed'], total_time)
            
            # Generate report
            generate_ocr_report(rfq_id, result.get("results", []), total_time)

            return {
                "ocr_results": result["results"],
                "current_step": "process_attachments",
            }
        except Exception as e:
            await session.rollback()
            total_time = time.time() - start_time
            error_traceback = traceback.format_exc()
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            logger.error(f"[OCR] ERROR processing RFQ {rfq_id}: {error_msg}")
            logger.error(f"[OCR] Traceback:\n{error_traceback}")
            
            # Log to OCR file
            log_ocr_failure(rfq_id, e, error_traceback)
            
            return {
                "ocr_results": [],
                "current_step": "process_attachments",
                "error": error_msg,
                "error_traceback": error_traceback,
            }
