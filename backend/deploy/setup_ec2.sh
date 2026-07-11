#!/bin/bash
set -e

# =============================================================
# ProcureGPT EC2 Deployment Script
# Run this on a fresh Ubuntu 24.04 EC2 instance as the ubuntu user
# Usage: bash setup_ec2.sh
# =============================================================

echo "=========================================="
echo "  ProcureGPT EC2 Deployment"
echo "=========================================="

# --- Configuration (edit these before running) ---
MYSQL_ROOT_PASSWORD="ProcureGPT@2026"
MYSQL_APP_USER="procuregpt"
MYSQL_APP_PASSWORD="ProcureGPT_DB@2026"
MYSQL_DATABASE="procuregpt"
APP_DIR="/opt/AI-ProcurementGPT"
REPO_URL="https://github.com/harshavardhanjagdale/AI-ProcurementGPT.git"  # Set your git repo URL here

# --- Step 1: System Update & Dependencies ---
echo ""
echo "[1/8] Installing system dependencies..."
sudo apt update && sudo apt upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    mysql-server \
    nginx \
    certbot python3-certbot-nginx \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    git \
    curl \
    build-essential
echo "[1/8] Done."

# --- Step 2: Configure MySQL ---
echo ""
echo "[2/8] Configuring MySQL..."
sudo systemctl start mysql
sudo systemctl enable mysql

sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '${MYSQL_ROOT_PASSWORD}';"
sudo mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "
  CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS '${MYSQL_APP_USER}'@'localhost' IDENTIFIED BY '${MYSQL_APP_PASSWORD}';
  GRANT ALL PRIVILEGES ON ${MYSQL_DATABASE}.* TO '${MYSQL_APP_USER}'@'localhost';
  FLUSH PRIVILEGES;
"
echo "[2/8] MySQL configured. Database: ${MYSQL_DATABASE}, User: ${MYSQL_APP_USER}"

# --- Step 3: Clone Repository ---
echo ""
echo "[3/8] Setting up application directory..."
sudo mkdir -p ${APP_DIR}
sudo chown ubuntu:ubuntu ${APP_DIR}

if [ ! -d "${APP_DIR}/.git" ]; then
    git clone ${REPO_URL} ${APP_DIR}
else
    echo "Repository already exists. Skipping clone."
fi

cd ${APP_DIR}/backend

# --- Step 4: Python Virtual Environment ---
echo ""
echo "[4/8] Setting up Python environment..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "[4/8] Python packages installed."

# --- Step 5: Create .env file ---
echo ""
echo "[5/8] Creating .env file..."
cat > ${APP_DIR}/backend/.env << ENVEOF
APP_NAME=ProcureGPT
APP_ENV=production
SECRET_KEY=$(python3.12 -c "import secrets; print(secrets.token_hex(32))")
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=${MYSQL_APP_USER}
MYSQL_PASSWORD=${MYSQL_APP_PASSWORD}
MYSQL_DATABASE=${MYSQL_DATABASE}

ANTHROPIC_API_KEY=REPLACE_ME
ANTHROPIC_MODEL=claude-sonnet-5

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=REPLACE_ME
SMTP_PASSWORD=REPLACE_ME
SMTP_FROM_NAME=ProcureGPT

IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=REPLACE_ME
IMAP_PASSWORD=REPLACE_ME

EMAIL_PROVIDER=smtp
EMAIL_PROCESSING_MODE=polling
EMBEDDING_MODEL=all-MiniLM-L6-v2
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=25
WEBHOOK_TOKEN=procuregpt-webhook-secret-2026

CORS_ORIGINS=https://ai-procurement-gpt.vercel.app

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=REPLACE_ME
LANGSMITH_PROJECT=ProcureGPT
ENVEOF

echo "[5/8] .env created at ${APP_DIR}/backend/.env"
echo "  >>> IMPORTANT: Edit .env and replace all REPLACE_ME values! <<<"

# --- Step 6: Create required directories ---
mkdir -p ${APP_DIR}/backend/uploads/email_attachments
mkdir -p ${APP_DIR}/backend/uploads/purchase_orders
mkdir -p ${APP_DIR}/backend/logs
mkdir -p ${APP_DIR}/backend/data

# --- Step 7: Initialize Database ---
echo ""
echo "[6/8] Initializing database..."
cd ${APP_DIR}/backend
source venv/bin/activate
python -m scripts.init_db
python -m scripts.seed_suppliers
python -m scripts.generate_embeddings
echo "[6/8] Database initialized with tables, suppliers, and embeddings."

# --- Step 8: Create systemd services ---
echo ""
echo "[7/8] Creating systemd services..."

sudo tee /etc/systemd/system/procuregpt.service > /dev/null << 'SVCEOF'
[Unit]
Description=ProcureGPT Backend API
After=network.target mysql.service
Wants=mysql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/procuregpt/backend
Environment=PATH=/opt/procuregpt/backend/venv/bin:/usr/local/bin:/usr/bin
EnvironmentFile=/opt/procuregpt/backend/.env
ExecStart=/opt/procuregpt/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo tee /etc/systemd/system/procuregpt-email.service > /dev/null << 'SVCEOF'
[Unit]
Description=ProcureGPT Email Listener
After=network.target mysql.service procuregpt.service
Wants=mysql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/procuregpt/backend
Environment=PATH=/opt/procuregpt/backend/venv/bin:/usr/local/bin:/usr/bin
EnvironmentFile=/opt/procuregpt/backend/.env
ExecStart=/opt/procuregpt/backend/venv/bin/python -m scripts.email_listener
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable procuregpt procuregpt-email
sudo systemctl start procuregpt
sudo systemctl start procuregpt-email
echo "[7/8] Services created and started."

# --- Step 9: Configure Nginx ---
echo ""
echo "[8/8] Configuring Nginx..."

sudo tee /etc/nginx/sites-available/procuregpt > /dev/null << 'NGXEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
NGXEOF

sudo ln -sf /etc/nginx/sites-available/procuregpt /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
echo "[8/8] Nginx configured."

# --- Done ---
echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/procuregpt/backend/.env and fill in API keys"
echo "  2. Restart services: sudo systemctl restart procuregpt procuregpt-email"
echo "  3. Check status: sudo systemctl status procuregpt"
echo "  4. View logs: sudo journalctl -u procuregpt -f"
echo "  5. Update Vercel frontend env vars:"
echo "     NEXT_PUBLIC_API_URL=http://<YOUR_EC2_IP>/api/v1"
echo "     NEXT_PUBLIC_WS_URL=ws://<YOUR_EC2_IP>/api/v1"
echo ""
echo "Optional - Add HTTPS:"
echo "  sudo certbot --nginx -d yourdomain.com"
echo ""
