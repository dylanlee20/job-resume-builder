#!/bin/bash
# One-time setup script — run this on the VPS to enable auto-deploy
# Usage: bash /root/job-resume-builder/deploy/setup.sh

set -e

echo "=== NewWhale Auto-Deploy Setup ==="

APP_DIR="/root/job-resume-builder"

# Make deploy script executable
chmod +x "$APP_DIR/deploy/deploy.sh"

# Create virtual environment if it doesn't exist
if [ ! -d "$APP_DIR/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$APP_DIR/venv"
    echo "Installing dependencies..."
    "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
else
    echo "Virtual environment already exists, ensuring dependencies are up to date..."
    "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet
fi

# Install systemd services
cp /root/job-resume-builder/deploy/newwhale-app.service /etc/systemd/system/
cp /root/job-resume-builder/deploy/newwhale-webhook.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and start services
systemctl enable newwhale-app
systemctl enable newwhale-webhook
systemctl start newwhale-app
systemctl start newwhale-webhook

# Open port 9000 for webhook (if ufw is active)
if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
    ufw allow 9000/tcp
    echo "Opened port 9000 in firewall"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "App running on:     http://$(curl -s ifconfig.me):5002"
echo "Webhook listening:  http://$(curl -s ifconfig.me):9000/webhook"
echo ""
echo "NEXT STEP: Add this webhook URL on GitHub:"
echo "  1. Go to your repo -> Settings -> Webhooks -> Add webhook"
echo "  2. Payload URL: http://$(curl -s ifconfig.me):9000/webhook"
echo "  3. Content type: application/json"
echo "  4. Secret: (add GITHUB_WEBHOOK_SECRET to your .env file)"
echo "  5. Events: Just the push event"
echo ""
echo "Status commands:"
echo "  systemctl status newwhale-app"
echo "  systemctl status newwhale-webhook"
echo "  tail -f /var/log/newwhale-deploy.log"
