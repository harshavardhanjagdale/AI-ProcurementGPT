"""
Initialize the database - creates all tables.
Run: python -m scripts.init_db
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import engine
from app.models import Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
