import sys
sys.path.insert(0, '.')
import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal
import json

async def check():
    async with AsyncSessionLocal() as session:
        # Get latest session
        result = await session.execute(text('SELECT id, status, current_step, current_agent, progress_percentage FROM workflow_sessions ORDER BY created_at DESC LIMIT 1'))
        row = result.fetchone()
        
        if not row:
            print("No sessions found")
            return
            
        session_id, status, step, agent, progress = row
        
        print("\n" + "="*50)
        print("WORKFLOW SESSION STATUS")
        print("="*50)
        print(f"Status: {status}")
        print(f"Current Step: {step}")
        print(f"Current Agent: {agent}")
        print(f"Progress: {progress}%")
        
        # Get all steps
        result = await session.execute(text(
            'SELECT name, display_name, status, error_message FROM workflow_steps WHERE session_id = :sid ORDER BY order_index'
        ), {'sid': session_id})
        
        print("\n" + "="*50)
        print("WORKFLOW STEPS")
        print("="*50)
        for name, display_name, st, err in result.fetchall():
            status_icon = "[OK]" if st == "completed" else "[>>]" if st == "running" else "[  ]"
            print(f"\n{status_icon} {name}")
            print(f"   Display: {display_name}")
            print(f"   Status: {st}")
            if err:
                print(f"   ERROR: {err}")

asyncio.run(check())
