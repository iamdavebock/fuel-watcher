# fuel-watcher

SA fuel price monitor for the Renmark / Riverland region.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Add your token to .env — register at https://fuelprice.io/api/
```

## Usage

```bash
# Current prices in Renmark (default)
fuel check

# Different location
fuel check --location "Berri"

# Filter to a specific fuel type
fuel check --fuel-type Diesel

# List stations with IDs
fuel stations

# Watch prices (poll every 15 min, U91 only)
fuel watch --interval 15 --fuel-type U91

# Price history for a station
fuel history --station 1234 --fuel-type U91 --hours 72
```

## Environment

```
FUELPRICE_API_TOKEN=your_token_here
```

## Cache

Station lists are cached to `.cache/` for 6 hours. Use `--refresh` on any command to bust the cache.
