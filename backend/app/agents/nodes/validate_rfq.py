"""
Validate RFQ Node - Checks if parsed intent has enough data to proceed.
Only requires at least one identifiable item. Everything else is optional.
"""
import logging

from app.agents.state import ProcurementState

logger = logging.getLogger(__name__)


async def validate_rfq_data(state: ProcurementState) -> dict:
    """Validate parsed RFQ data — only product_name is truly required."""
    parsed = state.get("parsed_intent", {})

    if not parsed:
        return {"current_step": "validate_rfq_data", "error": "No parsed intent found"}

    # Only check if we have at least one item with a product name
    items = parsed.get("items", [])
    if not items or not any(item.get("product_name") for item in items):
        return {
            "parsed_intent": {
                **parsed,
                "is_complete": False,
                "clarification_needed": "What product or item do you need to procure?",
            },
            "current_step": "validate_rfq_data",
        }

    # Default quantity to 1 for items missing it
    for item in items:
        if not item.get("quantity"):
            item["quantity"] = 1
        if not item.get("unit"):
            item["unit"] = "units"

    parsed["items"] = items
    parsed["is_complete"] = True

    return {
        "parsed_intent": parsed,
        "current_step": "validate_rfq_data",
    }


def route_after_validation(state: ProcurementState) -> str:
    """Route based on validation result and whether a direct supplier is specified."""
    parsed = state.get("parsed_intent", {})

    if not parsed.get("is_complete", False):
        return "ask_user"

    # If user specified a direct supplier, skip vendor selection
    if parsed.get("direct_supplier"):
        return "direct_supplier"

    return "select_vendors"
