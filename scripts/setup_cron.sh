#!/bin/bash
# Setup cron job for daily Iran crisis updates

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Iran Crisis Simulator - Daily Update Cron Setup"
echo "================================================"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Cron entry (runs at 6 PM daily)
CRON_CMD="0 18 * * * cd $PROJECT_DIR && python3 scripts/daily_update.py --auto >> logs/daily_update.log 2>&1"

# Check if entry exists
crontab -l 2>/dev/null | grep -q "daily_update.py"

if [ $? -eq 0 ]; then
    echo "⚠️  Cron job already exists"
    echo ""
    echo "To update, edit your crontab:"
    echo "  crontab -e"
    echo ""
    echo "Replace with:"
    echo "  $CRON_CMD"
    echo ""
else
    # Confirm before installing
    echo "This will install a cron job that runs daily at 6 PM UTC:"
    echo "  $CRON_CMD"
    echo ""
    read -p "Install cron job? (y/N) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Ensure logs directory exists
        mkdir -p "$PROJECT_DIR/logs"

        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

        echo ""
        echo "✓ Daily update cron job installed"
        echo ""
        echo "Schedule: 6 PM UTC daily"
        echo "Logs: $PROJECT_DIR/logs/daily_update.log"
        echo ""
        echo "To view cron jobs:"
        echo "  crontab -l"
        echo ""
        echo "To remove this cron job:"
        echo "  crontab -e"
        echo "  (Delete the line containing 'daily_update.py')"
        echo ""
    else
        echo ""
        echo "Installation cancelled"
        echo ""
    fi
fi
