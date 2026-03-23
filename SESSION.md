# fuel-watcher — Session State

## Last Session
- **Date:** 2026-03-23
- **Status:** CLI built and verified working

## Completed
- Project scaffold created (Ember init)
- Full Python CLI implemented with click + rich + httpx
  - `fuel check` — price table, cheapest highlighted green
  - `fuel watch` — polling with up/down diff indicators
  - `fuel history` — braille sparkline + min/max/avg panel
  - `fuel stations` — station list with IDs
- Graceful auth error handling (no token, invalid token, rate limit)
- 6-hour local station cache in `.cache/`
- `--refresh` flag on check/stations to bust cache
- venv at `.venv/`, installed with `pip install -e ".[dev]"`
- `fuel --help` confirmed working
- No-token error message confirmed displaying correctly

## In Progress
- Awaiting API token registration at https://fuelprice.io/api/

## Next Steps (priority order)
1. Register at fuelprice.io/api/ and add token to `.env`
2. Run `fuel stations` to verify Renmark station list
3. Run `fuel check` to see current prices
4. Optionally run `fuel watch` in lead-up to Thursday 2026-03-27 trip

## Notes
- Availability: SA law requires stations to report unavailability within 30 min. Currently inferred from null price — need token to confirm if FuelPrice.io exposes an explicit `available` field. Easy to wire in once verified.
- Dave is heading to Renmark (Riverland) Thursday 2026-03-27 — primary use case for this tool.

## Blockers
- Need API token before any live data can be fetched

## Access
- CLI: `/mnt/agents/projects/fuel-watcher/.venv/bin/fuel`
- Register: https://fuelprice.io/api/
