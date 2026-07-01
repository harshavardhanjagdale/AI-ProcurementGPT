"""
Background worker that periodically polls IMAP inbox for supplier replies.
Integrates with the email service to process and store incoming quotations.
"""
import asyncio
import logging

from app.database.connection import AsyncSessionLocal
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60


class EmailPollingWorker:
    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None

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
            try:
                await self._check_emails()
            except Exception as e:
                logger.error(f"Error in email polling cycle: {e}", exc_info=True)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _check_emails(self):
        """Single polling cycle: check inbox and process replies."""
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

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error processing emails: {e}", exc_info=True)

    async def poll_once(self) -> list[dict]:
        """Run a single poll cycle (useful for manual triggers)."""
        async with AsyncSessionLocal() as session:
            try:
                service = EmailService(session)
                results = await service.check_inbox_for_replies()
                await session.commit()
                return results
            except Exception as e:
                await session.rollback()
                logger.error(f"Error in manual poll: {e}", exc_info=True)
                return []


email_worker = EmailPollingWorker()
