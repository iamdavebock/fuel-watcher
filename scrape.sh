#!/bin/bash
# Fuel watcher scraper — runs via cron
# Exits cleanly after 2026-03-30

set -e

# Stop after Monday 30 March 2026
EXPIRY="2026-03-31"
TODAY=$(date +%Y-%m-%d)
if [[ "$TODAY" > "$EXPIRY" ]]; then
    echo "Scraper expired. Remove from crontab."
    exit 0
fi

cd /mnt/agents/projects/fuel-watcher
source .venv/bin/activate
python scrape.py 2>> /tmp/fuel-watcher.log
