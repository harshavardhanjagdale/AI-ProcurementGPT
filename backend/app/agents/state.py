"""
LangGraph Procurement Workflow State Definition.
This defines the shared state that flows through the procurement automation graph.
"""
from typing import Annotated, Literal, TypedDict

from langgraph.graph import add_messages


class ProcurementState(TypedDict):
    rfq_id: str
    user_id: str
    workflow_run_id: str

    user_input: str
    parsed_intent: dict

    selected_suppliers: list[dict]
    supplier_scores: list[dict]

    rfq_email_drafts: list[dict]
    rfq_emails_sent: bool

    received_emails: list[dict]
    ocr_results: list[dict]
    quotations: list[dict]

    comparison_matrix: dict
    ai_recommendation: dict
    rankings: list[dict]

    user_decision: Literal["approve", "negotiate", "cancel"] | None
    # The quotation the user picked (single-select) to approve into a PO or to negotiate.
    # None → fall back to the AI-recommended quotation.
    selected_quotation_id: str | None
    negotiation_targets: list[dict]

    negotiation_round: int
    negotiation_emails_sent: bool
    negotiation_results: list[dict]

    po_generated: bool
    po_pdf_path: str | None
    po_email_sent: bool

    current_step: str
    error: str | None
    messages: Annotated[list, add_messages]

    # OCR validation flags (used for routing back to waiting)
    no_quotations_yet: bool
    validation_failed: bool
    validation_message: str | None

    # Supplier names whose quotations were newly created in the most recent ocr_extract
    # run — used to post a "quotation received from X" chat line as replies stagger in.
    newly_received_suppliers: list[str]

    # Set when a supplier replies to a negotiation with text only (no revised quotation),
    # indicating they won't budge on price. Routes to user_decision_gate so the user can
    # approve at the original rate or cancel.
    negotiation_rejected: bool
    negotiation_rejection_summary: str | None

    # Generalized supplier text-reply analysis (pre-LLM classification).
    # Set when a supplier replies without a quotation PDF — the LLM classifies the reply
    # so the chat shows the actual supplier intent instead of "no PDF found".
    # Types: out_of_stock, alternative_offer, will_respond_later, general_inquiry, irrelevant
    supplier_reply_type: str | None
    supplier_reply_summary: str | None
    supplier_reply_alternative: dict | None
