#!/usr/bin/env python3
"""Check for unprocessed emails and manually trigger webhook if needed."""

import asyncio
import httpx
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.email import Email
from app.models.rfq import RFQ

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build database URL
DB_URL = f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"

async def check_unprocessed_emails():
    """Check for emails that haven't triggered OCR yet."""
    engine = create_async_engine(DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get all incoming emails
        result = await session.execute(
            select(Email)
            .where(Email.direction == "inbound")
            .order_by(Email.received_at.desc())
        )
        emails = result.scalars().all()
        
        logger.info(f"Total incoming emails: {len(emails)}")
        
        for email in emails[:3]:
            logger.info(f"\nEmail: {email.from_address}")
            logger.info(f"  Subject: {email.subject}")
            logger.info(f"  Received: {email.received_at}")
            logger.info(f"  RFQ ID: {email.rfq_id}")
            
            # Check if RFQ is stuck at process_attachments
            rfq_result = await session.execute(select(RFQ).where(RFQ.id == email.rfq_id))
            rfq = rfq_result.scalar_one_or_none()
            
            if rfq:
                logger.info(f"  RFQ Number: {rfq.rfq_number}")
                
                # Manually trigger webhook
                logger.info(f"\n[TRIGGER] Calling webhook for email from {email.from_address}")
                
                payload = {
                    "sender": email.from_address,
                    "to": email.to_address,
                    "subject": email.subject,
                    "body": email.body,
                    "attachments": []
                }
                
                headers = {
                    "X-Webhook-Token": settings.WEBHOOK_TOKEN,
                    "Content-Type": "application/json"
                }
                
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.post(
                            "http://localhost:8000/api/v1/webhook/email-arrived",
                            json=payload,
                            headers=headers
                        )
                        logger.info(f"Webhook response: {response.status_code}")
                        if response.status_code != 200:
                            logger.error(f"Response: {response.text}")
                        else:
                            logger.info(f"Response: {response.json()}")
                except Exception as e:
                    logger.error(f"Error calling webhook: {e}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_unprocessed_emails())
