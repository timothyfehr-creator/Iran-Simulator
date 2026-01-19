#!/bin/bash
# Enhanced cron wrapper with lock file, logging, and alerts
# Portable: computes PROJECT_DIR from script location

# Compute PROJECT_DIR dynamically (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

LOCK_FILE="$PROJECT_DIR/.daily_update.lock"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_update.log"
ALERT_EMAIL="${DAILY_UPDATE_EMAIL:-}"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Timestamp function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - CRON - $1" >> "$LOG_FILE"
}

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if ps -p "$PID" > /dev/null 2>&1; then
        log "ERROR: Previous run still in progress (PID $PID)"
        exit 1
    else
        log "WARNING: Stale lock file found, removing"
        rm "$LOCK_FILE"
    fi
fi

# Create lock with current PID
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$PROJECT_DIR"
log "Starting daily update pipeline"

# Run pipeline with set +e to prevent early exit before alerting
set +e
python3 scripts/daily_update.py \
    --auto-ingest \
    --strict-coverage \
    >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -eq 0 ]; then
    log "Pipeline completed successfully"
else
    log "ERROR: Pipeline failed with exit code $EXIT_CODE"

    # Send alert email if configured AND mail command exists
    if [ -n "$ALERT_EMAIL" ]; then
        if command -v mail > /dev/null 2>&1; then
            LATEST_RUN=$(ls -t runs/ 2>/dev/null | grep "RUN_.*_daily" | head -1)
            SUBJECT="[ALERT] Iran Simulation Daily Update FAILED"
            if [ -n "$LATEST_RUN" ] && [ -f "runs/$LATEST_RUN/alerts.json" ]; then
                mail -s "$SUBJECT" "$ALERT_EMAIL" < "runs/$LATEST_RUN/alerts.json"
            else
                echo "Pipeline failed. Check logs at $LOG_FILE" | mail -s "$SUBJECT" "$ALERT_EMAIL"
            fi
        else
            log "WARNING: DAILY_UPDATE_EMAIL is set but 'mail' command not found - cannot send alert"
        fi
    fi
fi

exit $EXIT_CODE
