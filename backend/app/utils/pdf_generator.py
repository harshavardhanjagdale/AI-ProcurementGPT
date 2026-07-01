"""
Purchase Order PDF Generator using ReportLab.
Creates professional PO documents with company branding.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)

from app.core.config import settings


class POPDFGenerator:
    def __init__(self):
        self.output_dir = Path(settings.UPLOAD_DIR) / "purchase_orders"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="POTitle",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#1a56db"),
            fontName="Helvetica-Bold",
        ))
        self.styles.add(ParagraphStyle(
            name="POSubtitle",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#4b5563"),
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="FieldLabel",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#6b7280"),
            fontName="Helvetica",
        ))
        self.styles.add(ParagraphStyle(
            name="FieldValue",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1f2937"),
            fontName="Helvetica-Bold",
        ))

    def generate(
        self,
        po_number: str,
        rfq_number: str,
        supplier_name: str,
        supplier_email: str,
        supplier_address: str | None,
        items: list[dict],
        total_amount: float,
        currency: str,
        delivery_date: str,
        payment_terms: str,
        shipping_address: str | None = None,
        company_name: str = "ProcureGPT",
    ) -> str:
        """
        Generate a Purchase Order PDF.

        Returns:
            Path to the generated PDF file
        """
        filename = f"{po_number}.pdf"
        filepath = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        elements = []

        # Header
        elements.append(Paragraph("PURCHASE ORDER", self.styles["POTitle"]))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(po_number, self.styles["POSubtitle"]))
        elements.append(Spacer(1, 4))
        elements.append(HRFlowable(
            width="100%", thickness=2, color=colors.HexColor("#1a56db")
        ))
        elements.append(Spacer(1, 16))

        # PO Details Table
        details_data = [
            ["PO Number:", po_number, "Date:", datetime.now(timezone.utc).strftime("%B %d, %Y")],
            ["RFQ Reference:", rfq_number, "Delivery Date:", delivery_date],
            ["Payment Terms:", payment_terms, "Currency:", currency],
        ]

        details_table = Table(details_data, colWidths=[90, 160, 90, 160])
        details_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (3, 0), (3, -1), colors.HexColor("#1f2937")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 20))

        # Supplier Info
        elements.append(Paragraph("SUPPLIER", self.styles["SectionHeader"]))
        elements.append(Paragraph(supplier_name, self.styles["FieldValue"]))
        elements.append(Paragraph(supplier_email, self.styles["Normal"]))
        if supplier_address:
            elements.append(Paragraph(supplier_address, self.styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Shipping Address
        if shipping_address:
            elements.append(Paragraph("SHIP TO", self.styles["SectionHeader"]))
            elements.append(Paragraph(shipping_address, self.styles["Normal"]))
            elements.append(Spacer(1, 12))

        # Items Table
        elements.append(Paragraph("ORDER ITEMS", self.styles["SectionHeader"]))
        elements.append(Spacer(1, 6))

        table_header = ["#", "Item Description", "Qty", "Unit Price", "Total"]
        table_data = [table_header]

        for i, item in enumerate(items, 1):
            table_data.append([
                str(i),
                item["product_name"],
                str(item["quantity"]),
                f"{currency} {item['unit_price']:,.2f}",
                f"{currency} {item['total_price']:,.2f}",
            ])

        # Total row
        table_data.append(["", "", "", "TOTAL:", f"{currency} {total_amount:,.2f}"])

        col_widths = [30, 220, 50, 90, 100]
        items_table = Table(table_data, colWidths=col_widths)
        items_table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),

            # Data rows
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),

            # Total row
            ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f9ff")),

            # Grid
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1a56db")),

            # Alternating rows
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),

            # Padding
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 30))

        # Terms & Conditions
        elements.append(Paragraph("TERMS & CONDITIONS", self.styles["SectionHeader"]))
        terms = [
            "1. This purchase order is subject to the agreed terms and conditions.",
            "2. Please acknowledge receipt of this order within 2 business days.",
            "3. Any discrepancies must be reported immediately before shipment.",
            f"4. Payment will be processed as per terms: {payment_terms}.",
            "5. Goods must be delivered by the specified delivery date.",
        ]
        for term in terms:
            elements.append(Paragraph(term, ParagraphStyle(
                name="Term", fontSize=8, leading=12, textColor=colors.HexColor("#4b5563"),
                spaceBefore=2,
            )))

        elements.append(Spacer(1, 40))

        # Signature line
        elements.append(HRFlowable(width="40%", thickness=0.5, color=colors.HexColor("#9ca3af")))
        elements.append(Paragraph("Authorized Signature", self.styles["FieldLabel"]))
        elements.append(Spacer(1, 20))

        # Footer
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e5e7eb")))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            f"Generated by {company_name} | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle(name="Footer", fontSize=7, textColor=colors.HexColor("#9ca3af"), alignment=1),
        ))

        # Build PDF
        doc.build(elements)
        return str(filepath)


pdf_generator = POPDFGenerator()
