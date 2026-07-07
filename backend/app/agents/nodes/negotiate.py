"""
Negotiation Node - Generates AI-powered negotiation emails for suppliers.
Supports multi-round negotiation with strategy.
"""
import logging

from app.agents.state import ProcurementState
from app.ai.llm_client import llm_client
from app.database.connection import AsyncSessionLocal
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

NEGOTIATION_PROMPT = """You are a skilled procurement negotiator. Write a concise negotiation message to a supplier requesting a revised price.

Context:
- Supplier: {supplier_name}
- Product: {product_description}
- Quantity: {quantity} units
- Their rate: {currency} {original_per_piece:,.2f}/unit (Total: {currency} {original_price:,.2f})
- Our target: {currency} {target_per_piece:,.2f}/unit (Total: {currency} {target_price:,.2f})
- Round: {round_number}

Rules:
- Write 2 short paragraphs ONLY. No salutation, no sign-off, no bullet points.
- Be direct: state the gap, mention competitive alternatives (no names), and propose the target.
- If round > 1, briefly acknowledge the previous offer.
- Emphasise long-term partnership value.
- Do NOT repeat the exact price numbers excessively — the email template already shows them in a table."""


async def negotiate_with_suppliers(state: ProcurementState) -> dict:
    """Generate and send negotiation emails to target suppliers."""
    rfq_id = state.get("rfq_id")
    targets = state.get("negotiation_targets", [])
    current_round = state.get("negotiation_round", 0) + 1
    parsed = state.get("parsed_intent", {})

    if not targets:
        return {
            "negotiation_round": current_round,
            "current_step": "negotiate_with_suppliers",
            "error": "No negotiation targets specified",
        }

    product_desc = parsed.get("title", "procurement items")
    default_currency = parsed.get("currency", "USD")

    results = []
    for target in targets:
        supplier_name = target.get("supplier_name", "Supplier")
        original_price = target.get("original_price", 0)
        target_price = target.get("target_price", 0)
        quantity = target.get("quantity") or 1
        # Prefer the quotation's own currency (set when the counter-offer is built) so the
        # email shows the right symbol rather than the parsed-intent default.
        currency = target.get("currency") or default_currency

        prompt = NEGOTIATION_PROMPT.format(
            supplier_name=supplier_name,
            currency=currency,
            quantity=quantity,
            original_price=original_price,
            target_price=target_price,
            original_per_piece=(original_price / quantity) if quantity else original_price,
            target_per_piece=(target_price / quantity) if quantity else target_price,
            round_number=current_round,
            product_description=product_desc,
        )

        negotiation_message = await llm_client.generate(
            system_prompt="You are an expert procurement negotiator.",
            user_prompt=prompt,
            max_tokens=800,
        )

        # Send negotiation email
        async with AsyncSessionLocal() as session:
            try:
                email_service = EmailService(session)
                send_result = await email_service.send_negotiation_email(
                    rfq_id=rfq_id,
                    supplier_id=target["supplier_id"],
                    round_number=current_round,
                    original_price=original_price,
                    target_price=target_price,
                    negotiation_message=negotiation_message,
                    sender_name="Procurement Team",
                    quantity=quantity,
                    gst_percent=target.get("gst_percent"),
                )
                await session.commit()

                results.append({
                    "supplier_id": target["supplier_id"],
                    "supplier_name": supplier_name,
                    "success": send_result["success"],
                    "message_preview": negotiation_message[:200],
                })
            except Exception as e:
                await session.rollback()
                logger.error(f"Negotiation email failed for {supplier_name}: {e}")
                results.append({
                    "supplier_id": target["supplier_id"],
                    "supplier_name": supplier_name,
                    "success": False,
                    "error": str(e),
                })

    sent_count = sum(1 for r in results if r["success"])
    logger.info(f"Sent {sent_count}/{len(results)} negotiation emails (round {current_round})")

    return {
        "negotiation_round": current_round,
        "negotiation_emails_sent": sent_count > 0,
        "negotiation_results": results,
        "current_step": "negotiate_with_suppliers",
    }


def route_negotiation_result(state: ProcurementState) -> str:
    """Route after negotiation: check if accepted or need another round."""
    results = state.get("negotiation_results", [])
    current_round = state.get("negotiation_round", 1)

    # Check if any negotiation was accepted
    if any(r.get("accepted") for r in results):
        return "generate_purchase_order"

    # Max 3 rounds
    if current_round >= 3:
        return "present_recommendation"

    return "await_negotiation_reply"
