"""
WebSocket endpoint for real-time workflow progress updates.

Single persistent connection per client. Clients authenticate with a JWT
token (query param), then subscribe to session IDs. The server fans out
progress events from the centralized WorkflowEventBus.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import decode_token
from app.database.connection import AsyncSessionLocal
from app.models.workflow_session import WorkflowSession
from app.models.workflow_step import WorkflowStep
from app.models.conversation_message import ConversationMessage
from app.workflows.event_bus import workflow_event_bus

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30


def _step_dict(s: WorkflowStep) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "display_name": s.display_name,
        "status": s.status,
        "agent": s.agent,
        "order_index": s.order_index,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "execution_time_ms": s.execution_time_ms,
        "error_message": s.error_message,
    }


async def _build_state_sync(session_id: str, user_id: str) -> dict | None:
    """Build a full state_sync payload from the database for reconnection recovery."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowSession).where(
                WorkflowSession.id == session_id,
                WorkflowSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        steps_result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.session_id == session_id)
            .order_by(WorkflowStep.order_index)
        )
        steps = list(steps_result.scalars().all())

        msgs_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .limit(100)
        )
        messages = list(msgs_result.scalars().all())

        return {
            "type": "state_sync",
            "workflowId": session_id,
            "currentStep": session.current_step,
            "totalSteps": len(steps),
            "progress": session.progress_percentage,
            "currentAgent": session.current_agent,
            "status": session.status,
            "title": session.title,
            "message": None,
            "timestamp": session.updated_at.isoformat() if session.updated_at else None,
            "steps": [_step_dict(s) for s in steps],
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "message_type": m.message_type,
                    "metadata": m.metadata_json,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }


async def _validate_session_ownership(session_id: str, user_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowSession.id).where(
                WorkflowSession.id == session_id,
                WorkflowSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None


@router.websocket("/ws/workflow")
async def workflow_websocket(websocket: WebSocket):
    # Must accept first, then authenticate via the first message or query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    await websocket.accept()
    logger.info(f"[WS] Client connected: user={user_id}")

    subscriptions: dict[str, asyncio.Queue] = {}
    fan_out_task: asyncio.Task | None = None
    heartbeat_task: asyncio.Task | None = None

    async def _fan_out():
        """Read from all subscribed queues and send to WebSocket."""
        while True:
            if not subscriptions:
                await asyncio.sleep(0.1)
                continue
            queues = list(subscriptions.values())
            sent_any = False
            for q in queues:
                try:
                    event = q.get_nowait()
                    await websocket.send_json(event)
                    sent_any = True
                except asyncio.QueueEmpty:
                    pass
                except Exception:
                    break
            if not sent_any:
                await asyncio.sleep(0.05)

    async def _heartbeat():
        """Send periodic pings to keep the connection alive."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break

    try:
        fan_out_task = asyncio.create_task(_fan_out())
        heartbeat_task = asyncio.create_task(_heartbeat())

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")
            session_id = msg.get("sessionId")

            if action == "subscribe" and session_id:
                if session_id in subscriptions:
                    continue

                if not await _validate_session_ownership(session_id, user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Access denied for session {session_id}",
                    })
                    continue

                queue = await workflow_event_bus.subscribe(session_id)
                subscriptions[session_id] = queue
                logger.info(f"[WS] user={user_id} subscribed to session={session_id}")

                cached = workflow_event_bus.get_latest_state(session_id)
                if cached:
                    await websocket.send_json(cached)
                else:
                    sync = await _build_state_sync(session_id, user_id)
                    if sync:
                        await websocket.send_json(sync)

            elif action == "unsubscribe" and session_id:
                q = subscriptions.pop(session_id, None)
                if q:
                    await workflow_event_bus.unsubscribe(session_id, q)
                    logger.info(f"[WS] user={user_id} unsubscribed from session={session_id}")

            elif action == "pong":
                pass

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected: user={user_id}")
    except Exception as e:
        logger.error(f"[WS] Error for user={user_id}: {e}", exc_info=True)
    finally:
        if fan_out_task:
            fan_out_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        await workflow_event_bus.unsubscribe_all(subscriptions)
        logger.info(f"[WS] Cleaned up {len(subscriptions)} subscriptions for user={user_id}")
