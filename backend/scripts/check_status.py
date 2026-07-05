import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from app.database.connection import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("SELECT id, title, status, current_step, rfq_id, progress_percentage FROM workflow_sessions ORDER BY created_at DESC LIMIT 5"))
        print("=== WORKFLOW SESSIONS ===")
        for row in r.fetchall():
            print(f"  ID: {row[0]}")
            print(f"  Title: {row[1]}")
            print(f"  Status: {row[2]}")
            print(f"  Step: {row[3]}")
            print(f"  RFQ: {row[4]}")
            print(f"  Progress: {row[5]}%")
            print("  ---")

        # Check emails for RFQs
        r2 = await s.execute(text("SELECT e.rfq_id, e.from_address, e.subject, e.direction, e.received_at FROM emails e WHERE e.direction='inbound' ORDER BY e.created_at DESC LIMIT 5"))
        print("\n=== INBOUND EMAILS ===")
        for row in r2.fetchall():
            print(f"  RFQ: {row[0]} | From: {row[1]} | Subject: {row[2][:50]} | At: {row[4]}")

asyncio.run(main())
