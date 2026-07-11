"""Create the llm_settings table."""
import asyncio
import sys
sys.path.insert(0, ".")

from app.database.connection import engine
from app.models.base import Base
from app.models.llm_settings import LLMSettings  # noqa: F401


async def create_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[LLMSettings.__table__])
    await engine.dispose()
    print("llm_settings table created successfully.")


if __name__ == "__main__":
    asyncio.run(create_table())
