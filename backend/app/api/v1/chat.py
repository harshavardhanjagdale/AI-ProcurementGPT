"""
Chat API - Natural language interface for RFQ creation and workflow management.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.chat_history import ChatHistory
from app.schemas.rfq import RFQFromChatRequest
from app.services.rfq_service import RFQService
from app.workflows.procurement_workflow import workflow_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    rfq_id: str | None = None
    workflow_id: str | None = None


class WorkflowDecisionRequest(BaseModel):
    workflow_id: str
    decision: str  # "approve", "negotiate", "cancel"
    negotiation_targets: list[dict] | None = None


@router.post("")
async def chat_with_ai(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Send a message to the AI procurement assistant.
    If no workflow exists, starts a new one. Otherwise continues conversation.
    """
    # Save user message to chat history
    user_msg = ChatHistory(
        user_id=current_user.id,
        rfq_id=data.rfq_id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.flush()

    # Start or resume workflow
    if data.workflow_id:
        result = await workflow_service.get_workflow_status(data.workflow_id)
        ai_response = _format_workflow_status(result)
    else:
        result = await workflow_service.start_workflow(
            user_input=data.message,
            user_id=current_user.id,
            rfq_id=data.rfq_id,
        )
        ai_response = _format_workflow_result(result)

    # Save AI response to chat history
    ai_msg = ChatHistory(
        user_id=current_user.id,
        rfq_id=data.rfq_id or result.get("state", {}).get("rfq_id"),
        role="assistant",
        content=ai_response["message"],
        metadata_json={"workflow_id": result.get("workflow_id")},
    )
    db.add(ai_msg)

    return {
        "response": ai_response["message"],
        "workflow_id": result.get("workflow_id"),
        "current_step": result.get("current_step"),
        "parsed_data": result.get("parsed_intent"),
        "suggested_suppliers": result.get("selected_suppliers", []),
        "requires_decision": result.get("current_step") == "user_decision_gate",
    }


@router.post("/decision")
async def submit_decision(
    data: WorkflowDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit a user decision (approve/negotiate/cancel) to resume workflow."""
    result = await workflow_service.resume_workflow(
        workflow_id=data.workflow_id,
        user_decision=data.decision,
        negotiation_targets=data.negotiation_targets,
    )

    # Save decision to chat
    decision_msg = ChatHistory(
        user_id=current_user.id,
        role="user",
        content=f"Decision: {data.decision}",
        metadata_json={"workflow_id": data.workflow_id, "decision": data.decision},
    )
    db.add(decision_msg)

    return {
        "workflow_id": data.workflow_id,
        "decision": data.decision,
        "current_step": result.get("current_step"),
        "message": _get_decision_response(data.decision, result),
    }


@router.get("/history")
async def get_chat_history(
    rfq_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get chat history for the current user."""
    from sqlalchemy import select

    query = (
        select(ChatHistory)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
    )

    if rfq_id:
        query = query.where(ChatHistory.rfq_id == rfq_id)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "rfq_id": m.rfq_id,
                "metadata": m.metadata_json,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(messages)
        ]
    }


@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(
    workflow_id: str,
    _current_user=Depends(get_current_user),
):
    """Get current status of a workflow."""
    return await workflow_service.get_workflow_status(workflow_id)


def _format_workflow_result(result: dict) -> dict:
    """Format workflow result into user-friendly message."""
    if result.get("error"):
        return {"message": f"Sorry, something went wrong: {result['error']}"}

    parsed = result.get("parsed_intent", {})
    suppliers = result.get("selected_suppliers", [])
    step = result.get("current_step", "")

    if not parsed.get("is_complete"):
        clarification = parsed.get("clarification_needed", "Could you provide more details?")
        return {"message": clarification}

    if suppliers:
        supplier_list = "\n".join(
            f"  {i+1}. {s['name']} ({s['country']}) - Rating: {s['rating']}/5"
            for i, s in enumerate(suppliers[:5])
        )
        return {
            "message": (
                f"I've parsed your request: **{parsed.get('title')}**\n\n"
                f"Found {len(suppliers)} matching suppliers:\n{supplier_list}\n\n"
                f"RFQ emails are being generated and will be sent shortly. "
                f"I'll notify you when supplier responses arrive."
            )
        }

    return {"message": f"Processing your request... Current step: {step}"}


def _format_workflow_status(result: dict) -> dict:
    """Format workflow status for display."""
    step = result.get("current_step", "unknown")
    status = result.get("status", "unknown")

    step_messages = {
        "parse_user_request": "Analyzing your request...",
        "select_vendors": "Finding matching suppliers...",
        "generate_rfq_emails": "Generating RFQ emails...",
        "send_rfq_emails": "Sending emails to suppliers...",
        "await_supplier_replies": "Waiting for supplier responses...",
        "process_attachments": "Processing received quotations...",
        "analyze_quotations": "Analyzing and comparing quotes...",
        "present_recommendation": "Analysis complete! Ready for your decision.",
        "user_decision_gate": "Awaiting your decision (approve/negotiate/cancel).",
        "generate_purchase_order": "Generating purchase order...",
        "send_po_email": "Sending purchase order to supplier...",
    }

    message = step_messages.get(step, f"Workflow is at step: {step} (status: {status})")
    return {"message": message}


def _get_decision_response(decision: str, result: dict) -> str:
    """Generate response after user decision."""
    if decision == "approve":
        return "Purchase order is being generated and will be sent to the supplier."
    elif decision == "negotiate":
        return "Negotiation emails are being prepared. I'll craft counter-offers based on market analysis."
    else:
        return "RFQ has been cancelled."
