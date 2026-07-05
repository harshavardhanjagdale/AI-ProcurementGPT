"""
Chat API - Natural language interface for RFQ creation and workflow management.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.database.connection import AsyncSessionLocal
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


class CheckEmailsRequest(BaseModel):
    workflow_id: str | None = None  # Optional: check emails for specific workflow


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
    # Convert empty strings to None for foreign key constraint
    rfq_id = data.rfq_id if data.rfq_id else None
    
    # Save user message to chat history
    user_msg = ChatHistory(
        user_id=current_user.id,
        rfq_id=rfq_id,
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
            rfq_id=rfq_id,
        )
        ai_response = _format_workflow_result(result)

    # Save AI response to chat history
    final_rfq_id = rfq_id or result.get("state", {}).get("rfq_id") or None
    ai_msg = ChatHistory(
        user_id=current_user.id,
        rfq_id=final_rfq_id,
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
        "workflow_url": f"/dashboard/workflows?workflow_id={result.get('workflow_id')}",
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


@router.post("/check-emails")
async def check_supplier_emails(
    data: CheckEmailsRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Manually trigger email check for supplier replies.
    If workflow_id provided, also resumes it if emails were found.
    
    This is useful when you want to manually check instead of waiting for background worker.
    """
    from app.email.background_worker import email_worker
    
    # Manually poll emails
    results = await email_worker.poll_once()
    
    message = f"Checked inbox. Found {len(results)} new supplier replies."
    workflow_status = None
    
    if data.workflow_id and results:
        # Check if workflow is at await_supplier_replies and has emails
        workflow_status = await workflow_service.get_workflow_status(data.workflow_id)
        
        if workflow_status.get("current_step") == "await_supplier_replies":
            message += f"\n✅ Workflow {data.workflow_id} has received replies. Auto-resuming..."
            
            # Resume the workflow to process attachments
            resume_result = await workflow_service.resume_workflow(data.workflow_id)
            workflow_status = {
                "workflow_id": data.workflow_id,
                "current_step": resume_result.get("current_step"),
                "status": "resumed",
                "message": "Workflow resumed to process quotations.",
            }
    
    return {
        "message": message,
        "emails_found": len(results),
        "details": results,
        "workflow_status": workflow_status,
    }


@router.get("/workflow/{workflow_id}/quotations")
async def get_workflow_quotations(
    workflow_id: str,
    _current_user=Depends(get_current_user),
):
    """
    Get all quotations received for a workflow's RFQ.
    Shows detailed status of each quote including AI analysis.
    """
    from sqlalchemy import select
    from app.models.quotation import Quotation
    from app.models.rfq import RFQ
    from app.models.supplier import Supplier
    
    async with AsyncSessionLocal() as session:
        # Get RFQ for this workflow
        result = await session.execute(
            select(RFQ).where(RFQ.ai_workflow_id == workflow_id)
        )
        rfq = result.scalar_one_or_none()
        
        if not rfq:
            return {
                "workflow_id": workflow_id,
                "error": "RFQ not found for this workflow",
                "quotations": [],
            }
        
        # Get all quotations for this RFQ
        result = await session.execute(
            select(Quotation).where(Quotation.rfq_id == rfq.id)
        )
        quotations = list(result.scalars().all())
        
        # Format with supplier info
        quotation_details = []
        for q in quotations:
            supplier_result = await session.execute(
                select(Supplier).where(Supplier.id == q.supplier_id)
            )
            supplier = supplier_result.scalar_one_or_none()
            
            quotation_details.append({
                "quotation_id": q.id,
                "supplier_name": supplier.name if supplier else "Unknown",
                "supplier_email": supplier.email if supplier else None,
                "total_amount": float(q.total_amount),
                "currency": q.currency,
                "delivery_days": q.delivery_days,
                "warranty_terms": q.warranty_terms,
                "payment_terms": q.payment_terms,
                "ai_score": float(q.ai_score) if q.ai_score else None,
                "ai_ranking": q.ai_ranking,
                "status": q.status,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            })
        
        return {
            "workflow_id": workflow_id,
            "rfq_id": rfq.id,
            "rfq_number": rfq.rfq_number,
            "quotations_count": len(quotations),
            "quotations": sorted(quotation_details, key=lambda x: x["ai_ranking"] or 999),
        }




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

    direct_supplier = parsed.get("direct_supplier")

    if suppliers and direct_supplier:
        supplier = suppliers[0]
        return {
            "message": (
                f"I've understood your request: **{parsed.get('title')}**\n\n"
                f"Direct purchase from: **{supplier['name']}**\n\n"
                f"RFQ email is being generated and sent directly to this supplier. "
                f"I'll notify you when their response arrives."
            )
        }

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
