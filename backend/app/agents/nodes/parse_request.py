"""
Parse User Request Node - Uses LLM to extract structured RFQ data
from natural language user input.
"""
import logging

from app.agents.state import ProcurementState
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

PARSE_SYSTEM_PROMPT = """You are a procurement assistant. Parse the user's natural language request into a structured RFQ (Request for Quotation).

Return a JSON object with:
{
    "title": "Short title for the RFQ",
    "description": "Detailed description",
    "items": [
        {
            "product_name": "Product name",
            "specifications": "Technical specs or null",
            "quantity": integer (default 1 if not specified),
            "unit": "units/kg/liters/etc (default 'units')"
        }
    ],
    "budget_min": float or null,
    "budget_max": float or null,
    "currency": "USD/EUR/INR/etc (default USD)",
    "delivery_deadline_days": integer or null,
    "categories": ["relevant supplier categories"],
    "direct_supplier": "supplier name if user explicitly wants to buy from a specific supplier, else null",
    "is_complete": true/false
}

IMPORTANT RULES:
- The ONLY mandatory fields are: at least one item with a product_name. Everything else is optional.
- If user doesn't mention quantity, default to 1.
- If user doesn't mention budget, currency, or deadline, leave them null. Still mark is_complete as true.
- If user says something like "buy from TechSupply Corp" or "order from GlobalTech", set "direct_supplier" to that supplier name.
- Set is_complete to false ONLY if you cannot identify even a single product/item from the message.
- Be generous with is_complete — if you can figure out what they want to buy, mark it true."""


async def parse_user_request(state: ProcurementState) -> dict:
    """Parse natural language input into structured RFQ data."""
    user_input = state["user_input"]

    logger.info(f"Parsing user request: {user_input[:100]}...")

    parsed = await llm_client.generate_json(
        system_prompt=PARSE_SYSTEM_PROMPT,
        user_prompt=user_input,
    )

    if parsed is None:
        return {
            "parsed_intent": {
                "is_complete": False,
                "clarification_needed": "I couldn't understand your request. Please describe what you need to procure.",
                "error": True,
            },
            "current_step": "parse_user_request",
        }

    logger.info(f"Parsed intent: {parsed.get('title')} - complete: {parsed.get('is_complete')}")

    return {
        "parsed_intent": parsed,
        "current_step": "parse_user_request",
    }
