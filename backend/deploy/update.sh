#!/bin/bash
set -e

# =============================================================
# ProcureGPT Update Script
# Run this on EC2 after pushing new code to git
# Usage: bash /opt/procuregpt/backend/deploy/update.sh
# =============================================================

APP_DIR="/opt/procuregpt"

echo "Pulling latest code..."
cd ${APP_DIR}
git pull

echo "Installing any new dependencies..."
cd ${APP_DIR}/backend
source venv/bin/activate
pip install -r requirements.txt --quiet

echo "Running database migrations..."
python -m scripts.init_db

echo "Restarting services..."
sudo systemctl restart procuregpt
sudo systemctl restart procuregpt-email

echo "Checking service status..."
sleep 2
sudo systemctl status procuregpt --no-pager -l | head -15
echo ""
sudo systemctl status procuregpt-email --no-pager -l | head -15

echo ""
echo "Update complete! Check logs: sudo journalctl -u procuregpt -f"
