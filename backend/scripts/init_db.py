"""
Initialize the database - creates the database (if needed) and all tables.
Run: python -m scripts.init_db
"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.database.connection import engine
from app.models import Base


async def ensure_database_exists():
    """Create the database if it doesn't exist."""
    server_url = (
        f"mysql+aiomysql://{settings.MYSQL_USER}:{quote_plus(settings.MYSQL_PASSWORD)}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/"
    )
    tmp_engine = create_async_engine(server_url, echo=False)
    async with tmp_engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    await tmp_engine.dispose()


async def init_db():
    await ensure_database_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init_db())
