#!/bin/zsh
# Scrape all stores and rebuild the site. Schedule with cron, e.g. 8am daily:
#   0 8 * * * /Users/jackroyle/claude/Desktop/Tracker/scripts/daily.sh
cd "$(dirname "$0")/.." && /usr/bin/env python3 -m tracker run >> data/scrape.log 2>&1
