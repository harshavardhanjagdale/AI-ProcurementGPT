FROM python:3.12-slim

# System deps for OCR (tesseract + poppler) and PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create dirs for uploads and checkpoints (ephemeral on Railway without volumes)
RUN mkdir -p uploads/email_attachments uploads/purchase_orders data logs

EXPOSE 8000

CMD ["python", "-m", "scripts.start"]
