"""
Background worker that periodically polls IMAP inbox for supplier replies.
Integrates with the email service to process and store incoming quotations.
"""
import asyncio
import logging

from app.database.connection import AsyncSessionLocal
from app.services.email_service import EmailService
from app.workflows.event_bus import workflow_event_bus

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15


class EmailPollingWorker:
    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None
        self._processing = False  # True while a graph resume is in progress

    async def start(self):
        """Start the background polling loop."""
        if self.running:
            logger.warning("Email polling worker is already running")
            return

        self.running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Email polling worker started (interval: {POLL_INTERVAL_SECONDS}s)")

    async def stop(self):
        """Stop the background polling loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Email polling worker stopped")

    async def _poll_loop(self):
        """Main polling loop that runs in the background."""
        while self.running:
            if self._processing:
                logger.debug("[WORKER] Skipping poll — graph resume still in progress")
            else:
                try:
                    await self._check_emails()
                except asyncio.CancelledError:
                    logger.warning("[WORKER] Poll cycle was cancelled")
                except Exception as e:
                    logger.error(f"Error in email polling cycle: {e}", exc_info=True)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _check_emails(self):
        """Single polling cycle: check inbox, process replies, and resume any waiting workflows."""
        await self._poll_and_resume()

    async def poll_once(self) -> list[dict]:
        """Run a single poll cycle (useful for manual triggers)."""
        return await self._poll_and_resume()

    async def _poll_and_resume(self) -> list[dict]:
        """
        Check the inbox for supplier replies, persist them, then resume the LangGraph
        checkpoint for any WorkflowSession that was waiting on one of those RFQs so
        OCR/analysis actually runs instead of just flipping a DB status flag.
        """
        to_resume: list[tuple[str, str]] = []
        results: list[dict] = []

        async with AsyncSessionLocal() as session:
            try:
                service = EmailService(session)
                results = await service.check_inbox_for_replies()

                if results:
                    logger.info(f"Processed {len(results)} new supplier replies")
                    for result in results:
                        logger.info(
                            f"  - RFQ {result['rfq_number']} from {result['supplier_email']} "
                            f"({result['attachments_count']} attachments)"
                        )

                    # Mark waiting WorkflowSessions as active (instant UI feedback)
                    # and collect their LangGraph thread IDs to resume below.
                    to_resume = await self._update_waiting_sessions(session, results)

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error processing emails: {e}", exc_info=True)
                return []

        # Resume graphs only after the email/attachment rows above are committed,
        # so the process_attachments node can actually see them.
        if to_resume:
            from app.workflows.session_workflow import session_workflow_service
            from app.models.base import generate_uuid, ist_now

            self._processing = True
            try:
                for session_id, thread_id, chat_content in to_resume:
                    logger.info(f"[WORKER] Publishing WS event for session {session_id}")
                    await workflow_event_bus.publish(session_id, {
                        "type": "workflow_progress",
                        "workflowId": session_id,
                        "currentStep": "ocr_extract",
                        "totalSteps": 12,
                        "progress": 66,
                        "currentStage": "Evaluation",
                        "currentAgent": "OCR Agent",
                        "status": "active",
                        "message": chat_content,
                        "timestamp": ist_now().isoformat(),
                        "chatMessage": {
                            "id": generate_uuid(),
                            "role": "assistant",
                            "content": chat_content,
                            "message_type": "event",
                            "created_at": ist_now().isoformat(),
                        },
                    })
                    logger.info(f"[WORKER] Resuming graph for session={session_id}, thread={thread_id}")

                    # Retry up to 2 times on CancelledError (transient network/TLS issue)
                    max_retries = 2
                    for attempt in range(max_retries + 1):
                        try:
                            result = await session_workflow_service.resume_after_reply(session_id, thread_id)
                            logger.info(f"[WORKER] Graph resume RESULT for {session_id}: {result}")
                            break
                        except asyncio.CancelledError:
                            if attempt < max_retries:
                                logger.warning(f"[WORKER] Graph resume CancelledError for {session_id}, retrying ({attempt+1}/{max_retries})...")
                                await asyncio.sleep(2)
                            else:
                                logger.error(f"[WORKER] Graph resume CancelledError for {session_id} after {max_retries} retries")
                        except Exception as e:
                            logger.error(f"[WORKER] Graph resume FAILED for {session_id}: {e}", exc_info=True)
                            break
            finally:
                self._processing = False

        return results

    async def _update_waiting_sessions(self, session, results: list[dict]) -> list[tuple[str, str]]:
        """Mark WorkflowSessions as active when a supplier reply arrives for their RFQ.

        Returns [(session_id, langgraph_thread_id), ...] for sessions that should
        have their LangGraph checkpoint resumed once this transaction is committed.
        """
        from sqlalchemy import select, update
        from app.models.workflow_session import WorkflowSession
        from app.models.workflow_step import WorkflowStep
        from app.models.workflow_event import WorkflowEvent
        from app.models.conversation_message import ConversationMessage
        from app.models.base import generate_uuid, ist_now

        rfq_ids = {r["rfq_id"] for r in results if r.get("rfq_id")}
        if not rfq_ids:
            return []

        # Find waiting sessions for these RFQs
        result = await session.execute(
            select(WorkflowSession).where(
                WorkflowSession.rfq_id.in_(rfq_ids),
                WorkflowSession.status == "waiting",
            )
        )
        waiting_sessions = list(result.scalars().all())

        rfq_attachment_counts = {r["rfq_id"]: r.get("attachments_count", 0) for r in results}

        to_resume = []
        for ws in waiting_sessions:
            if not ws.langgraph_thread_id:
                logger.warning(f"[WORKFLOW] Session {ws.id} has no langgraph_thread_id, cannot resume")
                continue

            ws.current_step = "ocr_extract"
            ws.current_agent = "OCR Agent"
            ws.status = "active"
            ws.progress_percentage = 66.0

            # Update step statuses
            await session.execute(
                update(WorkflowStep).where(
                    WorkflowStep.session_id == ws.id,
                    WorkflowStep.name == "await_supplier_replies",
                ).values(status="completed", completed_at=ist_now())
            )
            await session.execute(
                update(WorkflowStep).where(
                    WorkflowStep.session_id == ws.id,
                    WorkflowStep.name == "ocr_extract",
                ).values(status="running", started_at=ist_now())
            )

            has_attachments = rfq_attachment_counts.get(ws.rfq_id, 0) > 0

            # Add event
            event = WorkflowEvent(
                id=generate_uuid(),
                session_id=ws.id,
                event_type="step_completed",
                title="Supplier Response Received",
                description="A supplier has responded." if not has_attachments else "A supplier has responded with a quotation.",
                agent="Inbox Agent",
            )
            session.add(event)

            # Chat notification — different message depending on whether attachments exist
            if has_attachments:
                chat_content = "📩 A supplier has responded with a quotation! I'm now processing the attachment to extract pricing details..."
            else:
                chat_content = "📩 A supplier has responded. Analyzing their reply..."
            msg = ConversationMessage(
                id=generate_uuid(),
                session_id=ws.id,
                role="assistant",
                content=chat_content,
                message_type="event",
            )
            session.add(msg)

            logger.info(f"[WORKFLOW] Updated session {ws.id} - supplier replied for RFQ {ws.rfq_id} (attachments={has_attachments})")
            to_resume.append((ws.id, ws.langgraph_thread_id, msg.content))

        return to_resume


email_worker = EmailPollingWorker()
