"""
Centralized async pub/sub event bus for real-time workflow progress.

Each WebSocket connection subscribes a queue to one or more session IDs.
When a workflow node completes and _persist_node_progress commits, it calls
publish() which fans the event out to every queue watching that session.
"""
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkflowEventBus:
    """In-process async fan-out hub: session_id -> set[asyncio.Queue]."""

    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._latest_state: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers[session_id].add(queue)
        logger.debug(f"[EVENT-BUS] Subscribed to {session_id} (total: {len(self._subscribers[session_id])})")
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]
        logger.debug(f"[EVENT-BUS] Unsubscribed from {session_id}")

    async def unsubscribe_all(self, queues: dict[str, asyncio.Queue]) -> None:
        async with self._lock:
            for sid, q in queues.items():
                self._subscribers[sid].discard(q)
                if not self._subscribers[sid]:
                    self._subscribers.pop(sid, None)

    async def publish(self, session_id: str, event: dict) -> None:
        self._latest_state[session_id] = event
        async with self._lock:
            subscribers = list(self._subscribers.get(session_id, set()))
        dead: list[asyncio.Queue] = []
        for q in subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
                logger.warning(f"[EVENT-BUS] Dropping slow subscriber for {session_id}")
        if dead:
            async with self._lock:
                for q in dead:
                    self._subscribers[session_id].discard(q)

    def get_latest_state(self, session_id: str) -> dict | None:
        return self._latest_state.get(session_id)

    def has_subscribers(self, session_id: str) -> bool:
        return bool(self._subscribers.get(session_id))


workflow_event_bus = WorkflowEventBus()
