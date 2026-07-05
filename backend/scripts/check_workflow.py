#!/usr/bin/env python3
"""Check workflow session and OCR processing status."""
import asyncio
from sqlalchemy import text
from app.database.connection import AsyncSessionLocal

async def check_status():
    async with AsyncSessionLocal() as session:
        # Get latest workflow session
        result = await session.execute(text("""
            SELECT id, title, status, current_step, current_agent, progress_percentage, started_at, completed_at
            FROM workflow_sessions
            ORDER BY created_at DESC
            LIMIT 1
        """))
        session_row = result.fetchone()
        if session_row:
            print("\n=== LATEST WORKFLOW SESSION ===")
            print(f"ID: {session_row[0]}")
            print(f"Title: {session_row[1]}")
            print(f"Status: {session_row[2]}")
            print(f"Current Step: {session_row[3]}")
            print(f"Current Agent: {session_row[4]}")
            print(f"Progress: {session_row[5]}%")
            print(f"Started: {session_row[6]}")
            print(f"Completed: {session_row[7]}")
            
            session_id = session_row[0]
            
            # Get workflow steps
            result = await session.execute(text("""
                SELECT name, display_name, status, agent, started_at, completed_at, error_message
                FROM workflow_steps
                WHERE session_id = %s
                ORDER BY order_index
            """), {"session_id": session_id})
            
            print("\n=== WORKFLOW STEPS ===")
            for row in result.fetchall():
                print(f"\n{row[0]} ({row[1]})")
                print(f"  Status: {row[2]}")
                print(f"  Agent: {row[3]}")
                print(f"  Started: {row[4]}")
                print(f"  Completed: {row[5]}")
                if row[6]:
                    print(f"  ERROR: {row[6]}")
            
            # Get RFQ ID
            result = await session.execute(text("""
                SELECT rfq_id FROM workflow_sessions WHERE id = :session_id
            """), {"session_id": session_id})
            rfq_row = result.fetchone()
            
            if rfq_row and rfq_row[0]:
                rfq_id = rfq_row[0]
                print(f"\n=== EMAILS FOR RFQ {rfq_id} ===")
                result = await session.execute(text("""
                    SELECT id, status, subject, received_at
                    FROM emails
                    WHERE rfq_id = :rfq_id
                    ORDER BY received_at DESC
                """), {"rfq_id": rfq_id})
                
                for row in result.fetchall():
                    print(f"\nEmail ID: {row[0]}")
                    print(f"  Status: {row[1]}")
                    print(f"  Subject: {row[2]}")
                    print(f"  Received: {row[3]}")
                    
                    # Get attachments
                    att_result = await session.execute(text("""
                        SELECT file_name, ocr_processed
                        FROM email_attachments
                        WHERE email_id = :email_id
                    """), {"email_id": row[0]})
                    
                    for att_row in att_result.fetchall():
                        print(f"    - Attachment: {att_row[0]} (OCR: {att_row[1]})")
        else:
            print("No workflow sessions found")

asyncio.run(check_status())
