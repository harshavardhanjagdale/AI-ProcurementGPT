"""
OCR Recovery Script - Resets stuck OCR process and prepares for retry
"""
import asyncio
from sqlalchemy import text, update
from app.database.connection import AsyncSessionLocal
from app.models.workflow_session import WorkflowSession
from app.models.workflow_step import WorkflowStep
from app.models.base import ist_now
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

async def reset_stuck_ocr():
    """Reset stuck OCR process."""
    async with AsyncSessionLocal() as session:
        try:
            # Get latest session
            result = await session.execute(text('''
                SELECT id, current_step, status
                FROM workflow_sessions 
                ORDER BY created_at DESC LIMIT 1
            '''))
            
            session_row = result.fetchone()
            if not session_row:
                print("No sessions found")
                return
            
            session_id, current_step, status = session_row
            
            print(f"\nCurrent Status:")
            print(f"  Session ID: {session_id}")
            print(f"  Current Step: {current_step}")
            print(f"  Status: {status}")
            
            if current_step == "process_attachments" and status == "active":
                print(f"\nFound stuck OCR process. Resetting...")
                
                # Mark process_attachments as failed
                await session.execute(
                    update(WorkflowStep).where(
                        WorkflowStep.session_id == session_id,
                        WorkflowStep.name == "process_attachments"
                    ).values(
                        status="failed",
                        error_message="OCR timeout - automatic reset",
                        completed_at=ist_now()
                    )
                )
                
                # Reset session
                await session.execute(
                    update(WorkflowSession).where(
                        WorkflowSession.id == session_id
                    ).values(
                        status="failed",
                        current_step="process_attachments",
                        current_agent="System"
                    )
                )
                
                await session.commit()
                print(f"✓ OCR process marked as failed")
                print(f"✓ Session reset to failed status")
                print(f"\nNow you need to:")
                print(f"1. Restart backend: python -m uvicorn app.main:app --reload")
                print(f"2. Send fresh test email")
                print(f"3. Watch logs/ocr_processing.log for detailed logging")
            else:
                print(f"No stuck OCR process found")
                print(f"Current step: {current_step}")
            
        except Exception as e:
            print(f"Error: {e}")
            await session.rollback()

asyncio.run(reset_stuck_ocr())
