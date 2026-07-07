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


async def ocr_extract(state: ProcurementState) -> dict:
    """
    Merged graph node: OCR the supplier attachments, analyze/rank the quotations, and
    prepare the recommendation — all under one node so the trace (LangSmith) and the UI
    show a single "OCR Extract" step instead of three. Composes the existing functions
    (process_attachments → analyze_quotations → present_recommendation) unchanged.

    If no quotations could be extracted (supplier replied without a document), the node
    signals the graph to loop back to await_supplier_replies rather than failing.
    """
    from app.agents.nodes.analyze_quotes import analyze_quotations
    from app.agents.nodes.user_decision import present_recommendation

    out: dict = {}

    ocr = await process_attachments(state)
    out.update(ocr)

    # If OCR produced nothing and there are no existing quotations for this RFQ,
    # don't fail — signal that we need to keep waiting for a proper document.
    analysis = await analyze_quotations({**state, **out})

    if analysis.get("error") == "No quotations found for this RFQ":
        logger.info(f"[OCR] No quotations extracted yet — will wait for proper document")
        out.update(analysis)
        out["current_step"] = "ocr_extract"
        out["error"] = None  # Clear error so workflow doesn't mark as failed
        out["no_quotations_yet"] = True
        return out

    out.update(analysis)

    recommendation = await present_recommendation({**state, **out})
    out.update(recommendation)

    out["current_step"] = "ocr_extract"
    return out


def route_after_ocr(state: ProcurementState) -> str:
    """If no quotations were extracted (no document), loop back to waiting."""
    if state.get("no_quotations_yet"):
        return "await_supplier_replies"
    return "user_decision_gate"
