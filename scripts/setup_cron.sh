#!/bin/bash
# Install cron job for daily Iran simulation updates

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_SCRIPT="$PROJECT_DIR/scripts/run_daily_cron.sh"

echo "Iran Crisis Simulator - Daily Update Cron Setup"
echo "================================================"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Make wrapper script executable
chmod +x "$CRON_SCRIPT"

# Default to 6 PM UTC (adjust as needed)
CRON_HOUR="${CRON_HOUR:-18}"
CRON_MINUTE="${CRON_MINUTE:-0}"

# Create cron entry
CRON_LINE="$CRON_MINUTE $CRON_HOUR * * * $CRON_SCRIPT"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "run_daily_cron.sh"; then
    echo "Cron job already installed. Current entry:"
    crontab -l | grep "run_daily_cron.sh"
    echo ""
    read -p "Replace with new entry? [y/N] " -n 1 -r
    echo ""
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove old entry
    crontab -l | grep -v "run_daily_cron.sh" | crontab -
fi

# Also remove old daily_update.py entries if present
if crontab -l 2>/dev/null | grep -q "daily_update.py"; then
    echo "Found old daily_update.py entry, removing..."
    crontab -l | grep -v "daily_update.py" | crontab -
fi

# Add new entry
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo ""
echo "Cron job installed:"
echo "  Schedule: Daily at ${CRON_HOUR}:$(printf '%02d' $CRON_MINUTE) UTC"
echo "  Script: $CRON_SCRIPT"
echo "  Logs: $PROJECT_DIR/logs/daily_update.log"
echo ""
echo "Features:"
echo "  - Lock file prevents concurrent runs"
echo "  - Coverage gates exit nonzero on FAIL"
echo "  - Email alerts (if DAILY_UPDATE_EMAIL is set)"
echo ""
echo "To set email alerts:"
echo "  export DAILY_UPDATE_EMAIL=your@email.com"
echo ""
echo "To customize schedule:"
echo "  CRON_HOUR=6 CRON_MINUTE=30 bash scripts/setup_cron.sh"
echo ""
echo "To view installed jobs:"
echo "  crontab -l"
echo ""
echo "To remove:"
echo "  crontab -l | grep -v run_daily_cron.sh | crontab -"
