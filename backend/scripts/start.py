"""
Railway startup script: initializes DB, seeds data if empty, then starts uvicorn.
Run: python -m scripts.start
"""
import asyncio
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def startup():
    from sqlalchemy import text
    from app.database.connection import engine, AsyncSessionLocal
    from app.models import Base
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine

    # 1. Create database if not exists
    print("[1/4] Ensuring database exists...")
    server_url = (
        f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/"
    )
    tmp_engine = create_async_engine(server_url, echo=False)
    async with tmp_engine.begin() as conn:
        await conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
    await tmp_engine.dispose()
    print("       Database ready.")

    # 2. Create all tables
    print("[2/4] Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("       Tables ready.")

    # 3. Seed suppliers if table is empty
    print("[3/4] Checking suppliers...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM suppliers"))
        count = result.scalar()
        if count == 0:
            print("       Seeding suppliers...")
            await engine.dispose()
            from scripts.seed_suppliers import seed
            await seed()
            print("       Suppliers seeded.")

            print("[3b/4] Generating embeddings...")
            from scripts.generate_embeddings import generate_all_embeddings
            await generate_all_embeddings()
        else:
            print(f"       {count} suppliers already exist, skipping seed.")

    # 4. Dispose before handing off to uvicorn
    await engine.dispose()
    print("[4/4] Starting server...")


if __name__ == "__main__":
    asyncio.run(startup())

    port = os.environ.get("PORT", "8000")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", port,
    ])
