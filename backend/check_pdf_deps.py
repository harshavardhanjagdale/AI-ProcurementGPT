#!/usr/bin/env python3
"""Diagnose PDF processing dependencies."""

import subprocess
import sys

print("=" * 70)
print("PDF PROCESSING DIAGNOSTICS")
print("=" * 70)

# Check Tesseract
print("\n1. Tesseract OCR:")
try:
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
    print(f"   ✓ Installed: {result.stdout.split(chr(10))[0]}")
except FileNotFoundError:
    print("   ✗ NOT FOUND - Install: choco install tesseract or apt install tesseract-ocr")

# Check pdf2image
print("\n2. pdf2image (Python):")
try:
    import pdf2image
    print(f"   ✓ Installed: {pdf2image.__file__}")
except ImportError:
    print("   ✗ NOT FOUND - Install: pip install pdf2image")

# Check Ghostscript
print("\n3. Ghostscript:")
try:
    result = subprocess.run(["gs", "--version"], capture_output=True, text=True)
    print(f"   ✓ Installed: {result.stdout.strip()}")
except FileNotFoundError:
    print("   ✗ NOT FOUND - Install: choco install ghostscript or apt install ghostscript")

# Check poppler-utils (for Windows/Linux)
print("\n4. poppler-utils (for pdftoimage):")
try:
    result = subprocess.run(["pdftoppm", "--version"], capture_output=True, text=True)
    print(f"   ✓ Installed: {result.stdout.split(chr(10))[0]}")
except FileNotFoundError:
    print("   ✗ NOT FOUND - Install: choco install poppler or apt install poppler-utils")

# Test pdf2image with a simple conversion
print("\n5. Testing pdf2image conversion:")
try:
    from pdf2image import convert_from_path
    from pathlib import Path
    
    test_pdf = Path("./uploads/email_attachments/25_Alpha_Components_Quotation_RFQ-2026-00001_v2.pdf")
    if test_pdf.exists():
        print(f"   Testing with: {test_pdf}")
        try:
            images = convert_from_path(str(test_pdf), first_page=1, last_page=1)
            print(f"   ✓ Conversion successful! Got {len(images)} image(s)")
            print(f"   ✓ Image size: {images[0].size}")
        except Exception as e:
            print(f"   ✗ Conversion failed: {e}")
            print(f"\n   Common causes:")
            print(f"   - Ghostscript not installed")
            print(f"   - PDF file is corrupted")
            print(f"   - pdf2image not properly configured")
    else:
        print(f"   Test PDF not found: {test_pdf}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 70)
