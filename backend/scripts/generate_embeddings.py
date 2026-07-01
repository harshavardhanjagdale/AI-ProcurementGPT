"""
Generate embeddings for all suppliers in the database.
Run: python -m scripts.generate_embeddings
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update
from app.database.connection import AsyncSessionLocal
from app.models.supplier import Supplier
from app.models.supplier_category import SupplierCategory
from app.ai.embeddings import generate_embedding, serialize_embedding, build_supplier_profile_text


async def generate_all_embeddings():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Supplier).where(Supplier.status == "active")
        )
        suppliers = list(result.scalars().all())

        print(f"Generating embeddings for {len(suppliers)} suppliers...")

        for supplier in suppliers:
            cat_result = await session.execute(
                select(SupplierCategory).where(SupplierCategory.supplier_id == supplier.id)
            )
            categories = [c.category_name for c in cat_result.scalars().all()]

            profile_text = build_supplier_profile_text(
                name=supplier.name,
                categories=categories,
                country=supplier.country,
                notes=supplier.notes,
            )

            embedding = generate_embedding(profile_text)
            embedding_bytes = serialize_embedding(embedding)

            await session.execute(
                update(Supplier)
                .where(Supplier.id == supplier.id)
                .values(embedding_vector=embedding_bytes)
            )

            print(f"  ✓ {supplier.name} ({len(categories)} categories)")

        await session.commit()
        print(f"\nDone! Generated embeddings for {len(suppliers)} suppliers.")


if __name__ == "__main__":
    asyncio.run(generate_all_embeddings())
