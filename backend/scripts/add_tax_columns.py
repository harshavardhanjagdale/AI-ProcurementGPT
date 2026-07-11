"""Add tax columns to quotations and purchase_orders tables."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import engine

STATEMENTS = [
    "ALTER TABLE quotations ADD COLUMN tax_percent DECIMAL(5,2) NULL",
    "ALTER TABLE quotations ADD COLUMN tax_amount DECIMAL(15,2) NULL",
    "ALTER TABLE quotations ADD COLUMN grand_total DECIMAL(15,2) NULL",
    "ALTER TABLE purchase_orders ADD COLUMN subtotal DECIMAL(15,2) NULL",
    "ALTER TABLE purchase_orders ADD COLUMN tax_percent DECIMAL(5,2) NULL",
    "ALTER TABLE purchase_orders ADD COLUMN tax_amount DECIMAL(15,2) NULL",
]


async def migrate():
    from sqlalchemy import text

    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            col_name = stmt.split("ADD COLUMN ")[1].split(" ")[0]
            table = stmt.split("TABLE ")[1].split(" ")[0]
            try:
                await conn.execute(text(stmt))
                print(f"  + {table}.{col_name}")
            except Exception as e:
                if "Duplicate column" in str(e) or "already exists" in str(e):
                    print(f"  ~ {table}.{col_name} (already exists)")
                else:
                    print(f"  ! {table}.{col_name} FAILED: {e}")

    await engine.dispose()
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
