#!/usr/bin/env python3
"""Check attachments for RFQ."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.email_attachment import EmailAttachment
from pathlib import Path

# Build database URL
DB_URL = f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"

async def check():
    """Check attachments in database."""
    engine = create_async_engine(DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            select(EmailAttachment)
            .order_by(EmailAttachment.created_at.desc())
        )
        attachments = result.scalars().all()
        
        print(f"Total attachments: {len(attachments)}\n")
        
        for att in attachments[:5]:
            print(f"ID: {att.id}")
            print(f"  File: {att.file_name}")
            print(f"  Path: {att.file_path}")
            print(f"  Type: {att.file_type}")
            print(f"  Size: {att.file_size_bytes} bytes")
            print(f"  OCR Processed: {att.ocr_processed}")
            print(f"  Created: {att.created_at}\n")
            
            # Check if file exists
            if att.file_path:
                exists = Path(att.file_path).exists()
                print(f"  File exists: {exists}\n")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
