"""
Procurement Orchestrator - Main LangGraph workflow that controls the full RFQ lifecycle.
Defines the state machine graph with all nodes, edges, and interrupt points.
"""
import logging
from contextlib import AsyncExitStack
from pathlib import Path

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agents.state import ProcurementState
from app.agents.nodes.parse_request import parse_user_request
from app.agents.nodes.validate_rfq import validate_rfq_data, route_after_validation
from app.agents.nodes.create_rfq import create_rfq_record
from app.agents.nodes.direct_supplier import resolve_direct_supplier
from app.agents.nodes.select_vendors import select_vendors
from app.agents.nodes.generate_rfq import generate_rfq_emails
from app.agents.nodes.send_emails import send_rfq_emails
from app.agents.nodes.await_replies import await_supplier_replies
from app.agents.nodes.process_ocr import process_attachments
from app.agents.nodes.analyze_quotes import analyze_quotations
from app.agents.nodes.user_decision import (
    present_recommendation,
    user_decision_gate,
    route_user_decision,
)
from app.agents.nodes.negotiate import negotiate_with_suppliers, route_negotiation_result
from app.agents.nodes.generate_po import generate_purchase_order, send_po_email

logger = logging.getLogger(__name__)


def build_procurement_workflow() -> StateGraph:
    """
    Build the complete procurement automation workflow graph.

    Flow:
    START → parse_request → validate → [select_vendors | direct_supplier | ask_user]
    → create_rfq → generate_rfq → send_emails → await_replies
    → process_ocr → analyze_quotes → present_recommendation
    → user_decision → [approve→PO | negotiate→loop | cancel→END]

    Direct Purchase Flow:
    START → parse_request → validate → direct_supplier → create_rfq
    → generate_rfq → send_emails → await_replies → ...
    """
    workflow = StateGraph(ProcurementState)

    # Add all nodes
    workflow.add_node("parse_user_request", parse_user_request)
    workflow.add_node("validate_rfq_data", validate_rfq_data)
    workflow.add_node("create_rfq_record", create_rfq_record)
    workflow.add_node("resolve_direct_supplier", resolve_direct_supplier)
    workflow.add_node("select_vendors", select_vendors)
    workflow.add_node("generate_rfq_emails", generate_rfq_emails)
    workflow.add_node("send_rfq_emails", send_rfq_emails)
    workflow.add_node("await_supplier_replies", await_supplier_replies)
    workflow.add_node("process_attachments", process_attachments)
    workflow.add_node("analyze_quotations", analyze_quotations)
    workflow.add_node("present_recommendation", present_recommendation)
    workflow.add_node("user_decision_gate", user_decision_gate)
    workflow.add_node("negotiate_with_suppliers", negotiate_with_suppliers)
    workflow.add_node("generate_purchase_order", generate_purchase_order)
    workflow.add_node("send_po_email", send_po_email)

    # Set entry point
    workflow.set_entry_point("parse_user_request")

    # Define edges
    workflow.add_edge("parse_user_request", "validate_rfq_data")

    # Conditional: validation passes → multi-vendor OR direct supplier OR needs clarification
    workflow.add_conditional_edges(
        "validate_rfq_data",
        route_after_validation,
        {
            "select_vendors": "create_rfq_record",
            "direct_supplier": "resolve_direct_supplier",
            "ask_user": END,
        },
    )

    # Direct supplier flow → create RFQ → continue with RFQ generation
    workflow.add_edge("resolve_direct_supplier", "create_rfq_record")

    # Create RFQ in DB → then select vendors (for multi-vendor path)
    workflow.add_edge("create_rfq_record", "select_vendors")

    # Linear flow: vendors → RFQ generation → send
    workflow.add_edge("select_vendors", "generate_rfq_emails")
    workflow.add_edge("generate_rfq_emails", "send_rfq_emails")
    workflow.add_edge("send_rfq_emails", "await_supplier_replies")

    # After replies: OCR → Analysis → Recommendation
    workflow.add_edge("await_supplier_replies", "process_attachments")
    workflow.add_edge("process_attachments", "analyze_quotations")
    workflow.add_edge("analyze_quotations", "present_recommendation")
    workflow.add_edge("present_recommendation", "user_decision_gate")

    # User decision routing
    workflow.add_conditional_edges(
        "user_decision_gate",
        route_user_decision,
        {
            "generate_purchase_order": "generate_purchase_order",
            "negotiate_with_suppliers": "negotiate_with_suppliers",
            "__end__": END,
        },
    )

    # Negotiation → may loop back or proceed to PO
    workflow.add_conditional_edges(
        "negotiate_with_suppliers",
        route_negotiation_result,
        {
            "generate_purchase_order": "generate_purchase_order",
            "present_recommendation": "present_recommendation",
            "await_negotiation_reply": "await_supplier_replies",
        },
    )

    # PO → send email → END
    workflow.add_edge("generate_purchase_order", "send_po_email")
    workflow.add_edge("send_po_email", END)

    return workflow


DEFAULT_CHECKPOINT_DB_PATH = "./data/langgraph_checkpoints.sqlite"

# Set by init_procurement_graph() at app startup. `await_supplier_replies` and
# `user_decision_gate` can leave a workflow parked for real-world hours/days
# waiting on a human or a supplier email, so the checkpointer backing this
# graph must survive a backend restart (reload, crash, deploy) during that
# window — a plain in-memory MemorySaver silently loses that state, leaving
# WorkflowSession rows stuck "waiting" for a thread LangGraph no longer knows.
procurement_graph = None
_checkpointer_exit_stack: AsyncExitStack | None = None


async def init_procurement_graph(db_path: str | Path = DEFAULT_CHECKPOINT_DB_PATH):
    """
    Compile the workflow with interrupt points for human-in-the-loop, backed by
    a persistent SQLite checkpointer so pause/resume survives process restarts.
    """
    global procurement_graph, _checkpointer_exit_stack

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    exit_stack = AsyncExitStack()
    checkpointer = await exit_stack.enter_async_context(
        AsyncSqliteSaver.from_conn_string(str(db_path))
    )
    await checkpointer.setup()

    workflow = build_procurement_workflow()
    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["user_decision_gate"],
        interrupt_after=["await_supplier_replies"],
    )

    _checkpointer_exit_stack = exit_stack
    procurement_graph = compiled
    logger.info(f"Procurement graph compiled with persistent SQLite checkpointer at {db_path}")
    return procurement_graph


async def close_procurement_graph():
    """Close the checkpointer's SQLite connection on app shutdown."""
    global _checkpointer_exit_stack, procurement_graph
    if _checkpointer_exit_stack is not None:
        await _checkpointer_exit_stack.aclose()
        _checkpointer_exit_stack = None
    procurement_graph = None


def get_procurement_graph():
    """Return the compiled singleton graph. Raises if init_procurement_graph() hasn't run yet."""
    if procurement_graph is None:
        raise RuntimeError(
            "procurement_graph is not initialized - init_procurement_graph() "
            "must be awaited during app startup before it is used"
        )
    return procurement_graph
