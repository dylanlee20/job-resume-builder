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

# Ensure virtual environment exists
if [ ! -d "$APP_DIR/venv" ]; then
    echo "$(date): Creating virtual environment" >> "$LOG_FILE"
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    apt-get install -y -qq "python${PYTHON_VERSION}-venv" > /dev/null 2>&1 || true
    python3 -m venv "$APP_DIR/venv"
fi

# Install any new dependencies
"$APP_DIR/venv/bin/pip" install -r requirements.txt --quiet 2>> "$LOG_FILE"

# Restart the app
systemctl restart newwhale-app 2>> "$LOG_FILE" || echo "$(date): WARNING - systemctl restart failed, try manually" >> "$LOG_FILE"

echo "$(date): Deploy complete" >> "$LOG_FILE"
