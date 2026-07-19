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
from app.ai.llm_client import llm_client
from app.ocr.logger import (
    log_ocr_start, log_ocr_complete, log_ocr_failure,
    generate_ocr_report
)

logger = logging.getLogger(__name__)

SUPPLIER_REPLY_ANALYSIS_PROMPT = """You are a procurement email analyst. A buyer sent an RFQ (Request for Quotation) to a supplier. The supplier has replied with the email below — WITHOUT attaching a formal quotation document.

Classify the supplier's reply and extract key information.

Buyer's original request: {product_description}
{negotiation_context}

Supplier's reply:
---
{email_body}
---

Respond in this exact JSON format:
{{
  "type": "<one of: negotiation_rejection | out_of_stock | alternative_offer | will_respond_later | general_inquiry>",
  "summary": "one-sentence summary of the supplier's response in plain English",
  "alternative": null or {{"product": "product name/description", "brand": "brand if mentioned", "specs": "key specs if mentioned", "price": "price if mentioned, else null"}}
}}

Classification rules:
- "negotiation_rejection": Supplier explicitly refuses to lower their price (final price, best offer, cannot discount). Only use during a negotiation round.
- "out_of_stock": Supplier says the requested product is unavailable, out of stock, discontinued, or they don't deal in it.
- "alternative_offer": Supplier proposes a DIFFERENT product, brand, or specification than what was requested. Fill the "alternative" object.
- "will_respond_later": Supplier acknowledges the request and says they will send a quotation/response later.
- "general_inquiry": Supplier asks clarifying questions, provides general information, or any other response that doesn't fit above categories."""


async def _supplier_names_for_quotations(quotation_ids: list[str]) -> list[str]:
    """Look up the supplier names for a set of quotation ids (for the 'received from X' line)."""
    if not quotation_ids:
        return []
    from sqlalchemy import select
    from app.models.quotation import Quotation

    async with AsyncSessionLocal() as session:
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(Quotation)
            .options(selectinload(Quotation.supplier))
            .where(Quotation.id.in_(quotation_ids))
        )
        names = []
        for q in result.scalars().unique().all():
            if q.supplier and q.supplier.name and q.supplier.name not in names:
                names.append(q.supplier.name)
        return names


async def process_attachments(state: ProcurementState, *, skip_content_validation: bool = False) -> dict:
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
            logger.info(f"[OCR] Initializing OCR service for RFQ {rfq_id} (skip_content_validation={skip_content_validation})")
            service = OCRService(session)

            logger.info(f"[OCR] Processing attachments for RFQ {rfq_id}")
            result = await service.process_rfq_attachments(rfq_id, skip_content_validation=skip_content_validation)
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


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM output, handling markdown fences and preamble."""
    import json
    import re

    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


async def _analyze_supplier_reply(rfq_id: str, state: ProcurementState) -> dict | None:
    """Analyze the latest inbound email body for this RFQ using LLM classification.

    Returns {"type": str, "summary": str, "alternative": dict|None} or None if
    there's no relevant email body to analyze.
    """
    from sqlalchemy import select
    from app.models.email import Email

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Email)
            .where(Email.rfq_id == rfq_id, Email.direction == "inbound")
            .order_by(Email.received_at.desc())
            .limit(1)
        )
        latest_email = result.scalar_one_or_none()

    if not latest_email or not latest_email.body or len(latest_email.body.strip()) < 10:
        logger.info(f"[REPLY-ANALYSIS] No email body found for RFQ {rfq_id}")
        return None

    parsed_intent = state.get("parsed_intent", {})
    product_desc = parsed_intent.get("title", "procurement items")

    negotiation_round = state.get("negotiation_round", 0)
    negotiation_context = ""
    if negotiation_round > 0:
        targets = state.get("negotiation_targets", [])
        if targets:
            t = targets[0]
            negotiation_context = (
                f"Context: This is negotiation round {negotiation_round}. "
                f"Buyer counter-offered at {t.get('currency', 'USD')} {t.get('target_price', 0):,.2f} "
                f"against the supplier's quote of {t.get('currency', 'USD')} {t.get('original_price', 0):,.2f}."
            )

    logger.info(f"[REPLY-ANALYSIS] Analyzing supplier reply for RFQ {rfq_id} ({len(latest_email.body)} chars, negotiation_round={negotiation_round})")

    try:
        response = await llm_client.generate(
            system_prompt="You are a procurement email analyst. Respond only in valid JSON.",
            user_prompt=SUPPLIER_REPLY_ANALYSIS_PROMPT.format(
                product_description=product_desc,
                negotiation_context=negotiation_context,
                email_body=latest_email.body[:2000],
            ),
            max_tokens=300,
        )
        logger.info(f"[REPLY-ANALYSIS] LLM raw response: {response[:400]}")
        parsed = _extract_json(response)
        if parsed is None:
            logger.warning(f"[REPLY-ANALYSIS] Could not parse JSON from LLM response: {response[:200]}")
            return None

        result = {
            "type": parsed.get("type", "general_inquiry"),
            "summary": parsed.get("summary", "Supplier responded without a formal quotation."),
            "alternative": parsed.get("alternative"),
        }
        logger.info(f"[REPLY-ANALYSIS] Classification: {result}")
        return result
    except Exception as e:
        logger.error(f"[REPLY-ANALYSIS] Failed to analyze supplier reply: {e}", exc_info=True)
        return None


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
    rfq_id = state.get("rfq_id")

    logger.info(f"[OCR-EXTRACT] Starting. State has no_quotations_yet={state.get('no_quotations_yet')}, rfq_id={rfq_id}")

    # ── Pre-LLM: classify the supplier's email reply BEFORE OCR ──────────
    # This tells us whether the supplier is offering an alternative product,
    # rejecting negotiation, out of stock, etc. — so we can adjust the OCR
    # validation (e.g. skip product-name checks for alternative offers).
    reply_analysis = await _analyze_supplier_reply(rfq_id, state)
    reply_type = reply_analysis["type"] if reply_analysis else None
    is_alternative = reply_type == "alternative_offer"

    if reply_analysis:
        out["supplier_reply_type"] = reply_type
        out["supplier_reply_summary"] = reply_analysis["summary"]
        out["supplier_reply_alternative"] = reply_analysis.get("alternative")
        logger.info(f"[OCR-EXTRACT] Pre-LLM classification: '{reply_type}' — {reply_analysis['summary']}")

    # ── OCR: process attachments (bypass content validation for alternatives) ──
    ocr = await process_attachments(state, skip_content_validation=is_alternative)
    out.update(ocr)

    logger.info(
        f"[OCR-EXTRACT] process_attachments done: "
        f"validation_failed={out.get('validation_failed')}, "
        f"ocr_results_count={len(out.get('ocr_results', []))}, "
        f"successful={sum(1 for r in out.get('ocr_results', []) if r.get('success'))}"
    )

    # If validation failed (wrong sender, wrong items), go back to waiting.
    # Clear reply_type so the validation failure message takes priority in chat.
    if out.get("validation_failed"):
        logger.info("[OCR-EXTRACT] Validation failed — returning to supplier waiting")
        out["current_step"] = "ocr_extract"
        out["error"] = None
        out["no_quotations_yet"] = True
        out["supplier_reply_type"] = None
        out["supplier_reply_summary"] = None
        out["supplier_reply_alternative"] = None
        return out

    # Analyze quotations (existing + any newly extracted).
    analysis = await analyze_quotations({**state, **out})
    logger.info(f"[OCR-EXTRACT] analyze_quotations done: error={analysis.get('error')}, rankings={bool(analysis.get('rankings'))}")
    out.update(analysis)

    # Check if we got any NEW quotations from this run.
    new_quotation_ids = [
        r["quotation_id"]
        for r in out.get("ocr_results", [])
        if r.get("success") and r.get("quotation_id")
    ]

    # ── Handle text-only replies (no PDF attachment extracted) ────────────
    if not new_quotation_ids and reply_analysis:
        logger.info(f"[OCR-EXTRACT] No new quotations extracted, handling reply_type='{reply_type}'")

        if reply_type == "negotiation_rejection":
            out["negotiation_rejected"] = True
            out["negotiation_rejection_summary"] = reply_analysis["summary"]
            out["no_quotations_yet"] = False
            recommendation = await present_recommendation({**state, **out})
            out.update(recommendation)
            out["current_step"] = "ocr_extract"
            return out

        if reply_type == "alternative_offer":
            out["no_quotations_yet"] = False
            if out.get("rankings"):
                recommendation = await present_recommendation({**state, **out})
                out.update(recommendation)
            out["current_step"] = "ocr_extract"
            return out

        if reply_type in ("out_of_stock", "will_respond_later", "general_inquiry"):
            out["no_quotations_yet"] = True
            out["current_step"] = "ocr_extract"
            out["error"] = None
            return out

    # If there are truly no quotations at all, keep waiting.
    if out.get("error") == "No quotations found for this RFQ" or not out.get("rankings"):
        logger.info("[OCR-EXTRACT] No quotations/rankings — will wait for proper document")
        out["current_step"] = "ocr_extract"
        out["error"] = None
        out["no_quotations_yet"] = True
        return out

    # ── Post-LLM: quotations extracted successfully ──────────────────────
    out["newly_received_suppliers"] = await _supplier_names_for_quotations(new_quotation_ids)

    recommendation = await present_recommendation({**state, **out})
    out.update(recommendation)
    logger.info(f"[OCR-EXTRACT] Recommendation done. Rankings={bool(out.get('rankings'))}. Routing to user_decision_gate.")

    out["current_step"] = "ocr_extract"
    out["no_quotations_yet"] = False
    out["validation_failed"] = False
    out["validation_message"] = None
    out["negotiation_rejected"] = False
    out["negotiation_rejection_summary"] = None
    out["supplier_reply_type"] = None if not is_alternative else out.get("supplier_reply_type")
    out["supplier_reply_summary"] = None if not is_alternative else out.get("supplier_reply_summary")
    out["supplier_reply_alternative"] = None if not is_alternative else out.get("supplier_reply_alternative")
    return out


def route_after_ocr(state: ProcurementState) -> str:
    """Route after OCR based on what we found."""
    reply_type = state.get("supplier_reply_type")

    if state.get("negotiation_rejected"):
        logger.info("[ROUTE] route_after_ocr: negotiation_rejected -> user_decision_gate")
        return "user_decision_gate"

    if reply_type == "alternative_offer":
        logger.info("[ROUTE] route_after_ocr: alternative_offer -> user_decision_gate")
        return "user_decision_gate"

    if state.get("no_quotations_yet"):
        logger.info(f"[ROUTE] route_after_ocr: no_quotations_yet (reply_type={reply_type}) -> await_supplier_replies")
        return "await_supplier_replies"

    logger.info("[ROUTE] route_after_ocr -> user_decision_gate")
    return "user_decision_gate"
