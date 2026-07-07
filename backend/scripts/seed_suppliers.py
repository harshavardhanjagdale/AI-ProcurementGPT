"""
Seed script to populate the database with sample suppliers.
Run: python -m scripts.seed_suppliers
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import AsyncSessionLocal
from app.models.supplier import Supplier
from app.models.supplier_category import SupplierCategory
from app.models.base import generate_uuid

SAMPLE_SUPPLIERS = [
    {
        "name": "TechSupply Corp",
        "email": "techsupply@yopmail.com",
        "phone": "+1-555-0101",
        "country": "USA",
        "city": "San Francisco",
        "rating": 4.5,
        "avg_delivery_days": 7,
        "default_tax_percent": None,
        "categories": ["IT Hardware", "Laptops", "Networking Equipment"],
    },
    {
        "name": "GlobalTech Solutions",
        "email": "globaltech@yopmail.com",
        "phone": "+1-555-0102",
        "country": "USA",
        "city": "Austin",
        "rating": 4.2,
        "avg_delivery_days": 10,
        "default_tax_percent": None,
        "categories": ["IT Hardware", "Servers", "Storage Solutions"],
    },
    {
        "name": "Infosys Hardware Ltd",
        "email": "infosyshardware@yopmail.com",
        "phone": "+91-9876543210",
        "country": "India",
        "city": "Bangalore",
        "rating": 4.0,
        "avg_delivery_days": 14,
        "default_tax_percent": 18.0,
        "categories": ["IT Hardware", "Laptops", "Desktops"],
    },
    {
        "name": "EuroTech Supplies GmbH",
        "email": "eurotech@yopmail.com",
        "phone": "+49-30-12345678",
        "country": "Germany",
        "city": "Berlin",
        "rating": 4.7,
        "avg_delivery_days": 12,
        "default_tax_percent": 19.0,
        "categories": ["IT Hardware", "Enterprise Solutions", "Networking Equipment"],
    },
    {
        "name": "Dragon Electronics Co",
        "email": "dragonelectronics@yopmail.com",
        "phone": "+86-21-87654321",
        "country": "China",
        "city": "Shenzhen",
        "rating": 3.8,
        "avg_delivery_days": 21,
        "default_tax_percent": 13.0,
        "categories": ["IT Hardware", "Components", "Peripherals"],
    },
    {
        "name": "OfficeMax Supplies",
        "email": "officemax@yopmail.com",
        "phone": "+1-555-0201",
        "country": "USA",
        "city": "Chicago",
        "rating": 4.1,
        "avg_delivery_days": 5,
        "default_tax_percent": None,
        "categories": ["Office Supplies", "Furniture", "Stationery"],
    },
    {
        "name": "PrintWorks International",
        "email": "printworks@yopmail.com",
        "phone": "+44-20-12345678",
        "country": "UK",
        "city": "London",
        "rating": 4.3,
        "avg_delivery_days": 8,
        "default_tax_percent": 20.0,
        "categories": ["Printers", "Office Equipment", "Toner & Ink"],
    },
    {
        "name": "SecureNet Systems",
        "email": "securenet@yopmail.com",
        "phone": "+1-555-0301",
        "country": "USA",
        "city": "New York",
        "rating": 4.6,
        "avg_delivery_days": 10,
        "default_tax_percent": None,
        "categories": ["Cybersecurity", "Networking Equipment", "Firewalls"],
    },
    {
        "name": "CloudFirst Services",
        "email": "cloudfirst@yopmail.com",
        "phone": "+1-555-0401",
        "country": "USA",
        "city": "Seattle",
        "rating": 4.4,
        "avg_delivery_days": 3,
        "default_tax_percent": None,
        "categories": ["Cloud Services", "Software Licenses", "SaaS"],
    },
    {
        "name": "Nippon Electronics",
        "email": "nipponelectronics@yopmail.com",
        "phone": "+81-3-98765432",
        "country": "Japan",
        "city": "Tokyo",
        "rating": 4.8,
        "avg_delivery_days": 15,
        "default_tax_percent": 10.0,
        "categories": ["IT Hardware", "Displays", "Enterprise Solutions"],
    },

    # Additional Suppliers

    {
        "name": "Prime Industrial Supplies",
        "email": "primeindustrial@yopmail.com",
        "phone": "+1-555-0501",
        "country": "USA",
        "city": "Dallas",
        "rating": 4.3,
        "avg_delivery_days": 6,
        "default_tax_percent": None,
        "categories": ["Industrial Equipment", "Safety Equipment", "Tools"],
    },
    {
        "name": "Alpha Components",
        "email": "alphacomponents@yopmail.com",
        "phone": "+91-9988776655",
        "country": "India",
        "city": "Pune",
        "rating": 4.2,
        "avg_delivery_days": 8,
        "default_tax_percent": 18.0,
        "categories": ["Components", "Electronics", "Industrial Parts"],
    },
    {
        "name": "Mega Office Solutions",
        "email": "megaoffice@yopmail.com",
        "phone": "+44-20-99887766",
        "country": "UK",
        "city": "Manchester",
        "rating": 4.4,
        "avg_delivery_days": 5,
        "default_tax_percent": 20.0,
        "categories": ["Office Supplies", "Furniture"],
    },
    {
        "name": "Vertex Networking",
        "email": "vertexnetwork@yopmail.com",
        "phone": "+1-555-0601",
        "country": "USA",
        "city": "Boston",
        "rating": 4.7,
        "avg_delivery_days": 7,
        "default_tax_percent": None,
        "categories": ["Networking Equipment", "Firewalls", "Switches"],
    },
    {
        "name": "Zenith Technologies",
        "email": "zenithtech@yopmail.com",
        "phone": "+81-3-55667788",
        "country": "Japan",
        "city": "Osaka",
        "rating": 4.8,
        "avg_delivery_days": 12,
        "default_tax_percent": 10.0,
        "categories": ["Laptops", "Servers", "Storage Solutions"],
    },
    {
        "name": "Smart Office India",
        "email": "smartofficeindia@yopmail.com",
        "phone": "+91-9123456789",
        "country": "India",
        "city": "Hyderabad",
        "rating": 4.1,
        "avg_delivery_days": 6,
        "default_tax_percent": 18.0,
        "categories": ["Office Equipment", "Printers", "Furniture"],
    },
    {
        "name": "Pacific Electronics",
        "email": "pacificelectronics@yopmail.com",
        "phone": "+65-61234567",
        "country": "Singapore",
        "city": "Singapore",
        "rating": 4.6,
        "avg_delivery_days": 9,
        "default_tax_percent": 9.0,
        "categories": ["Displays", "Components", "Peripherals"],
    },
    {
        "name": "BlueSky Software",
        "email": "blueskysoftware@yopmail.com",
        "phone": "+1-555-0701",
        "country": "USA",
        "city": "Denver",
        "rating": 4.5,
        "avg_delivery_days": 2,
        "default_tax_percent": None,
        "categories": ["Software Licenses", "Cloud Services", "SaaS"],
    },
    {
        "name": "Elite Enterprise Systems",
        "email": "eliteenterprise@yopmail.com",
        "phone": "+49-30-44556677",
        "country": "Germany",
        "city": "Munich",
        "rating": 4.7,
        "avg_delivery_days": 10,
        "default_tax_percent": 19.0,
        "categories": ["Enterprise Solutions", "Servers", "Networking Equipment"],
    },
    {
        "name": "Rapid Procurement Ltd",
        "email": "rapidprocurement@yopmail.com",
        "phone": "+91-9988112233",
        "country": "India",
        "city": "Mumbai",
        "rating": 4.3,
        "avg_delivery_days": 4,
        "default_tax_percent": 18.0,
        "categories": ["Industrial Equipment", "Office Supplies", "IT Hardware"],
    },
]


async def seed():
    async with AsyncSessionLocal() as session:
        for supplier_data in SAMPLE_SUPPLIERS:
            categories = supplier_data.pop("categories")
            supplier = Supplier(id=generate_uuid(), **supplier_data, status="active")
            session.add(supplier)
            await session.flush()

            for cat_name in categories:
                category = SupplierCategory(
                    id=generate_uuid(),
                    supplier_id=supplier.id,
                    category_name=cat_name,
                )
                session.add(category)

        await session.commit()
        print(f"Successfully seeded {len(SAMPLE_SUPPLIERS)} suppliers.")


if __name__ == "__main__":
    asyncio.run(seed())
