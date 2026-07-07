"""Backfill default_tax_percent on existing supplier rows."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import engine
from sqlalchemy import text

COUNTRY_TAX = {
    "India": 18.0,
    "Germany": 19.0,
    "UK": 20.0,
    "Japan": 10.0,
    "China": 13.0,
    "Singapore": 9.0,
}


async def backfill():
    async with engine.begin() as conn:
        for country, pct in COUNTRY_TAX.items():
            r = await conn.execute(
                text("UPDATE suppliers SET default_tax_percent = :pct WHERE country = :c AND default_tax_percent IS NULL"),
                {"pct": pct, "c": country},
            )
            print(f"  {country} -> {pct}%  ({r.rowcount} rows)")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(backfill())
