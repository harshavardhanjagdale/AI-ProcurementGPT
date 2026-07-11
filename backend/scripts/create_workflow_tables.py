"""
Create workflow tables: workflow_sessions, workflow_steps, workflow_events, conversation_messages
Run: python scripts/create_workflow_tables.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import engine
from app.models.base import Base
from app.models import (
    WorkflowSession, WorkflowStep, WorkflowEvent, ConversationMessage
)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                WorkflowSession.__table__,
                WorkflowStep.__table__,
                WorkflowEvent.__table__,
                ConversationMessage.__table__,
            ]
        )
    await engine.dispose()
    print("[OK] Created tables: workflow_sessions, workflow_steps, workflow_events, conversation_messages")


if __name__ == "__main__":
    asyncio.run(create_tables())
