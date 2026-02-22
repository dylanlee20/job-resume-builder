#!/bin/bash
# Auto-deploy script for NewWhale Career
# Pulls latest code from GitHub and restarts the app

set -e

APP_DIR="/root/job-resume-builder"
BRANCH="master"
LOG_FILE="/var/log/newwhale-deploy.log"

echo "$(date): Deploy started" >> "$LOG_FILE"

cd "$APP_DIR"

# Pull latest code
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# Install any new dependencies
source venv/bin/activate 2>/dev/null || true
pip install -r requirements.txt --quiet 2>> "$LOG_FILE"

# Restart the app
systemctl restart newwhale-app 2>> "$LOG_FILE" || echo "$(date): WARNING - systemctl restart failed, try manually" >> "$LOG_FILE"

echo "$(date): Deploy complete" >> "$LOG_FILE"
