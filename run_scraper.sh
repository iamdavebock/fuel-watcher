#!/bin/bash
# fuel-watcher scraper — run via cron every 2 hours
set -e
cd /mnt/agents/projects/fuel-watcher
source .venv/bin/activate
python run_scraper.py 2>> /tmp/fuel-watcher.log
