#!/usr/bin/env bash
# Auto-deploy script for NewWhale Career Flask app on newwhaletech.com/.
# Triggered by .github/workflows/deploy.yml on every push to master.
# Uses flock to prevent concurrent runs.
set -euo pipefail

APP_DIR="/opt/app"
BRANCH="master"
LOG_FILE="/var/log/newwhale-deploy.log"
LOCK_FILE="/var/run/newwhale-deploy.lock"
SERVICE_NAME="newwhale"
HEALTH_URL="http://127.0.0.1:5002/auth/login"

exec 9>"$LOCK_FILE"
if ! flock -w 600 9; then
  echo "$(date -u +%FT%TZ): could not acquire deploy lock" | tee -a "$LOG_FILE"
  exit 1
fi

log() { echo "$(date -u +%FT%TZ): $*" | tee -a "$LOG_FILE"; }
fail() { log "FAIL: $*"; exit 1; }

run() {
  log "+ $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

log "deploy started (pid $$)"
cd "$APP_DIR"

# Note: the GH Actions workflow git-pulls the repo BEFORE invoking this
# script (so this script is always the latest version). We just record
# the current SHA here for logging.
GIT_SHA=$(git rev-parse --short HEAD)
log "at $GIT_SHA"

# Install any new Python deps if requirements changed
if git diff HEAD@{1} HEAD --name-only 2>/dev/null | grep -q "^requirements"; then
  log "requirements changed — pip install"
  run /opt/app/venv/bin/pip install -q -r requirements.txt
fi

# Apply migrations on every deploy. They are idempotent and — now that the
# one-time front-office backfill is marker-gated — cheap, so we no longer gate
# on a fragile `git diff HEAD@{1}` that silently skipped them after an
# interrupted deploy (and left half-applied state).
if [ -f /opt/app/migrations/run.py ]; then
  log "running migrations"
  run /opt/app/venv/bin/python /opt/app/migrations/run.py
fi

# Restart service
if /usr/bin/systemctl cat "${SERVICE_NAME}.service" >/dev/null 2>&1; then
  /usr/bin/systemctl restart "${SERVICE_NAME}"
  log "systemd ${SERVICE_NAME} restarted"
else
  fail "no systemd entry for ${SERVICE_NAME}"
fi

log "health check on $HEALTH_URL"
for attempt in 1 2 3 4 5 6 7 8; do
  sleep 2
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
  # /login returns 200 unauthenticated, /dashboard 302 — accept any 2xx/3xx
  if [[ "$STATUS" =~ ^[23] ]]; then
    log "health OK ($STATUS) — deploy complete (sha $GIT_SHA)"
    exit 0
  fi
  log "health attempt $attempt: $STATUS"
done

fail "health check did not return 2xx/3xx after restart (sha $GIT_SHA)"
