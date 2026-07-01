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
