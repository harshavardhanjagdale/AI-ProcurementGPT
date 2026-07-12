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
    
    log_ocr_start(rfq_id, 0)

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
            logger.info(
                f"[OCR] process_rfq_attachments returned: "
                f"total={result['total_processed']}, "
                f"successful={result['successful']}, "
                f"failed={result['failed']}, "
                f"results_detail={[{k: v for k, v in r.items() if k != 'raw_text'} for r in result.get('results', [])]}"
            )
            await session.commit()
            
            total_time = time.time() - start_time

            # Check if all results failed due to validation
            validation_failures = [
                r for r in result.get("results", [])
                if r.get("validation_reason")
            ]
            if validation_failures and result["successful"] == 0:
                details = "; ".join(r["validation_details"] for r in validation_failures)
                logger.warning(f"[OCR] All attachments failed validation: {details}")
                return {
                    "ocr_results": result["results"],
                    "current_step": "process_attachments",
                    "validation_failed": True,
                    "validation_message": details,
                }

            logger.info(
                f"[OCR] SUCCESS for RFQ {rfq_id}: "
                f"{result['successful']} success, {result['failed']} failed in {total_time:.2f}s"
            )
            
            log_ocr_complete(rfq_id, result['successful'], result['failed'], total_time)
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

    If quotation validation fails (wrong supplier or irrelevant items), the node signals
    a loop back to await_supplier_replies with a message explaining the issue.
    """
    from app.agents.nodes.analyze_quotes import analyze_quotations
    from app.agents.nodes.user_decision import present_recommendation

    out: dict = {}

    logger.info(f"[OCR-EXTRACT] Starting. State has no_quotations_yet={state.get('no_quotations_yet')}, rfq_id={state.get('rfq_id')}")

    ocr = await process_attachments(state)
    out.update(ocr)

    logger.info(
        f"[OCR-EXTRACT] process_attachments done: "
        f"validation_failed={out.get('validation_failed')}, "
        f"ocr_results_count={len(out.get('ocr_results', []))}, "
        f"successful={sum(1 for r in out.get('ocr_results', []) if r.get('success'))}"
    )

    # If validation failed (wrong sender, wrong items), go back to waiting
    if out.get("validation_failed"):
        logger.info(f"[OCR-EXTRACT] Validation failed — returning to supplier waiting")
        out["current_step"] = "ocr_extract"
        out["error"] = None
        out["no_quotations_yet"] = True
        return out

    # If OCR produced nothing and there are no existing quotations for this RFQ,
    # don't fail — signal that we need to keep waiting for a proper document.
    analysis = await analyze_quotations({**state, **out})
    logger.info(f"[OCR-EXTRACT] analyze_quotations done: error={analysis.get('error')}, rankings={bool(analysis.get('rankings'))}")

    if analysis.get("error") == "No quotations found for this RFQ":
        logger.info(f"[OCR-EXTRACT] No quotations found — will wait for proper document")
        out.update(analysis)
        out["current_step"] = "ocr_extract"
        out["error"] = None
        out["no_quotations_yet"] = True
        return out

    out.update(analysis)

    recommendation = await present_recommendation({**state, **out})
    out.update(recommendation)
    logger.info(f"[OCR-EXTRACT] Recommendation done. Rankings={bool(out.get('rankings'))}. Routing to user_decision_gate.")

    out["current_step"] = "ocr_extract"
    # Explicitly clear retry flags so the router doesn't loop back
    out["no_quotations_yet"] = False
    out["validation_failed"] = False
    out["validation_message"] = None
    return out


def route_after_ocr(state: ProcurementState) -> str:
    """If no quotations were extracted (no document), loop back to waiting."""
    decision = "user_decision_gate"
    if state.get("no_quotations_yet"):
        decision = "await_supplier_replies"
    logger.info(f"[ROUTE] route_after_ocr: no_quotations_yet={state.get('no_quotations_yet')} -> {decision}")
    return decision
