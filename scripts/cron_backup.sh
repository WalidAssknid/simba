#!/bin/bash

# SIMBA Automated Backup Script for Cron
# This script should be added to crontab for automated backups

cd "$(dirname "$0")"

# Source environment variables if needed
if [ -f ../.env ]; then
    source ../.env
fi

# Run the backup script
./backup.sh

# Optional: Clean up logs older than 30 days
find ../logs -name "*.log" -mtime +30 -delete 2>/dev/null || true

# Add to crontab with:
# 0 2 * * * /path/to/simba-2025/scripts/cron_backup.sh
# This runs daily at 2 AM 