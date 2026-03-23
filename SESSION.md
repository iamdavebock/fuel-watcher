# fuel-watcher — Session State

## Last Session
- **Date:** 2026-03-24
- **Status:** Live at fuel.davebock.au — multi-source static site with 2-hour VM cron

## Completed
- Strategy pivot: fuelprice.io abandoned (token never obtained) → PetrolSpy + FuelSnoop scraping
- Vercel serverless Python abandoned (PetrolSpy geo-blocks Vercel IPs) → static HTML served from `public/`
- VM cron fetches data every 2 hours → generates `public/index.html` → git push → Vercel auto-deploys
- Two sources: `scrape/sources/petrolspy.py`, `scrape/sources/fuelsnoop.py`
- Source rotation: `.scraper_state.json` (gitignored) ensures no consecutive hits to same source
- `run_scraper.py` orchestrator: picks source, generates HTML, commits and pushes
- `run_scraper.sh` cron wrapper with venv activation
- Page layout: Diesel table → Premium Diesel table → Red "No Price" section (out of stock / unreported)
- Stations grouped geographically in drive order: Gawler → Renmark
- Cheapest station highlighted, town group headers, staleness indicators
- Cron: `0 */2 * * *` installed for user `claude`
- Git credentials configured for headless push (`~/.git-credentials`)
- GitHub: `iamdavebock/fuel-watcher` → linked to Vercel project `prj_sKnfOdch5WDYAR77AnMXPL8JznZX`
- DNS: `fuel.davebock.au` CNAME → `cname.vercel-dns.com`

## In Progress
- Nothing — site is live and auto-updating

## Next Steps
1. Verify site looks correct before Thursday trip (2026-03-27)
2. Manual refresh if needed: `cd /mnt/agents/projects/fuel-watcher && source .venv/bin/activate && python run_scraper.py`
3. Decommission after trip (expires 2026-03-30)

## Blockers
- None

## Access
- Live site: https://fuel.davebock.au
- Cron log: `/tmp/fuel-watcher-cron.log`
- State file: `/mnt/agents/projects/fuel-watcher/.scraper_state.json`
