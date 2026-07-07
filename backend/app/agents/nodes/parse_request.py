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
    "description": "Detailed description of the procurement request",
    "items": [
        {
            "product_name": "Product name (include brand if mentioned, e.g. 'Dell Latitude Laptop')",
            "specifications": "Technical specs — ALWAYS provide this, see rules below",
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

specifications field (NEVER leave null):
- If the user provides specs (RAM, screen size, model number, color, etc.), use those exactly.
- If the user mentions a brand + product (e.g. "Dell Latitude laptops"), infer reasonable standard specs: "Dell Latitude series, business-grade, Intel Core i5/i7, 8-16 GB RAM, 256-512 GB SSD, 14-15.6 inch display".
- If the user only says a generic product (e.g. "laptops"), provide a sensible default: "Business laptop, Intel Core i5 or equivalent, 8 GB RAM, 256 GB SSD, 14-15.6 inch display, Windows OS".
- For non-tech items, describe key attributes: size, material, grade, standard, etc.
- NEVER set specifications to null. Always provide a meaningful description.

Other rules:
- The ONLY mandatory fields are: at least one item with a product_name. Everything else is optional.
- If user doesn't mention quantity, default to 1.
- If user doesn't mention budget, currency, or deadline, leave them null. Still mark is_complete as true.
- "direct_supplier" should ONLY be set when the user explicitly names a SUPPLIER/VENDOR they want to buy FROM (e.g. "buy from TechSupply Corp", "order from GlobalTech", "purchase from ErgoSupply").
- Do NOT set direct_supplier for product BRANDS or MANUFACTURERS in the product name. "Dell", "HP", "Lenovo", "Apple", "Samsung", etc. are product brands, NOT supplier names. "Buy 10 Dell laptops" means buy Dell-branded laptops from any supplier — direct_supplier should be null. "Buy 10 laptops from TechSupply" means buy from the supplier TechSupply — direct_supplier should be "TechSupply".
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


async def parse_and_validate(state: ProcurementState) -> dict:
    """
    Merged graph node: parse the natural-language request AND validate it in a single
    step, so the trace (LangSmith) and the UI show one "Understand Request" node instead
    of two. Internally it just composes the existing parse + validate logic unchanged.
    """
    from app.agents.nodes.validate_rfq import validate_rfq_data

    out: dict = {}
    parsed = await parse_user_request(state)
    out.update(parsed)
    validated = await validate_rfq_data({**state, **out})
    out.update(validated)
    out["current_step"] = "parse_request"
    return out
