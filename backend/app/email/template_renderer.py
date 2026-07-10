"""
Renders email HTML templates with Jinja2-style variable substitution.
Uses simple string replacement to avoid Jinja2 dependency for now.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(template_name: str) -> str:
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Email template not found: {template_name}")
    return template_path.read_text(encoding="utf-8")


def _render_simple(template: str, context: dict) -> str:
    """
    Simple template rendering with {{ variable }} and {% for %} / {% if %} support.
    For production, replace with Jinja2. This handles basic cases.
    """
    # Handle simple variable substitution
    for key, value in context.items():
        if not isinstance(value, (list, dict)):
            template = template.replace(f"{{{{ {key} }}}}", str(value or ""))

    # Handle {% if var %} ... {% endif %} blocks
    if_pattern = re.compile(r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL)
    for match in if_pattern.finditer(template):
        var_name = match.group(1)
        block_content = match.group(2)
        if context.get(var_name):
            template = template.replace(match.group(0), block_content)
        else:
            template = template.replace(match.group(0), "")

    # Handle {% for item in items %} ... {% endfor %} blocks
    for_pattern = re.compile(
        r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}", re.DOTALL
    )
    for match in for_pattern.finditer(template):
        item_var = match.group(1)
        list_var = match.group(2)
        loop_body = match.group(3)

        items = context.get(list_var, [])
        rendered_items = []
        for item in items:
            item_rendered = loop_body
            if isinstance(item, dict):
                for k, v in item.items():
                    item_rendered = item_rendered.replace(
                        f"{{{{ {item_var}.{k} }}}}", str(v or "N/A")
                    )
            rendered_items.append(item_rendered)

        template = template.replace(match.group(0), "".join(rendered_items))

    return template


def render_rfq_email(
    rfq_number: str,
    rfq_title: str,
    supplier_name: str,
    items: list[dict],
    sender_name: str,
    rfq_description: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    currency: str = "USD",
    delivery_deadline: str | None = None,
) -> str:
    template = _load_template("rfq_request.html")
    context = {
        "rfq_number": rfq_number,
        "rfq_title": rfq_title,
        "rfq_description": rfq_description,
        "supplier_name": supplier_name,
        "items": items,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "currency": currency,
        "delivery_deadline": delivery_deadline,
        "sender_name": sender_name,
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    return _render_simple(template, context)


def render_negotiation_email(
    rfq_number: str,
    supplier_name: str,
    round_number: int,
    original_price: float,
    target_price: float,
    currency: str,
    negotiation_message: str,
    sender_name: str,
    quantity: int = 1,
    gst_percent: float | None = None,
    original_quote_date: str | None = None,
    justification: str | None = None,
) -> str:
    template = _load_template("negotiation.html")

    unit_price = original_price / quantity if quantity else original_price
    target_unit_price = target_price / quantity if quantity else target_price
    gst_amount = original_price * gst_percent / 100 if gst_percent else 0

    context = {
        "rfq_number": rfq_number,
        "supplier_name": supplier_name,
        "round_number": str(round_number),
        "quantity": str(quantity),
        "unit_price": f"{unit_price:,.2f}",
        "original_price": f"{original_price:,.2f}",
        "target_unit_price": f"{target_unit_price:,.2f}",
        "target_price": f"{target_price:,.2f}",
        "gst_percent": f"{gst_percent:.1f}" if gst_percent else "",
        "gst_amount": f"{gst_amount:,.2f}" if gst_percent else "",
        "currency": currency,
        "negotiation_message": negotiation_message,
        "sender_name": sender_name,
        "justification": justification,
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    return _render_simple(template, context)


def render_purchase_order_email(
    po_number: str,
    rfq_number: str,
    supplier_name: str,
    items: list[dict],
    total_amount: float,
    currency: str,
    payment_terms: str,
    delivery_date: str,
    sender_name: str,
    shipping_address: str | None = None,
    company_name: str = "ProcureGPT",
    subtotal: float | None = None,
    tax_percent: float | None = None,
    tax_amount: float | None = None,
    intro_message: str | None = None,
) -> str:
    template = _load_template("purchase_order.html")
    context = {
        "po_number": po_number,
        "rfq_number": rfq_number,
        "supplier_name": supplier_name,
        # LLM-drafted opening line when provided; otherwise the standard sentence.
        "intro_message": intro_message
        or "We are pleased to confirm the following purchase order based on your accepted quotation:",
        "items": items,
        "subtotal": f"{subtotal:,.2f}" if subtotal else f"{total_amount:,.2f}",
        "tax_percent": f"{tax_percent:.1f}" if tax_percent else "",
        "tax_amount": f"{tax_amount:,.2f}" if tax_amount else "",
        "total_amount": f"{total_amount:,.2f}",
        "currency": currency,
        "payment_terms": payment_terms,
        "delivery_date": delivery_date,
        "order_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "shipping_address": shipping_address,
        "sender_name": sender_name,
        "company_name": company_name,
        "generated_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    return _render_simple(template, context)
