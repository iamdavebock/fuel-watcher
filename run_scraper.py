"""
Fuel-watcher scraper orchestrator.
Rotates between data sources (never hits the same one twice in a row),
generates public/index.html, and pushes to GitHub.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scrape.common import now_adelaide, route_index
from scrape.render import render_error_html, render_html
from scrape.sources import petrolspy

# --------------------------------------------------------------------------- #
# Source registry
# --------------------------------------------------------------------------- #

SOURCES = [petrolspy]

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

PROJECT_DIR = Path(__file__).parent
STATE_FILE = PROJECT_DIR / ".scraper_state.json"
OUTPUT_FILE = PROJECT_DIR / "public" / "index.html"


# --------------------------------------------------------------------------- #
# State management
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"last_source": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# --------------------------------------------------------------------------- #
# Source rotation
# --------------------------------------------------------------------------- #

def pick_source(last_source: str | None):
    """Return next source module, never repeating the last one used."""
    if last_source is None:
        return SOURCES[0]
    available = [s for s in SOURCES if s.SOURCE_NAME != last_source]
    return available[0] if available else SOURCES[0]


# --------------------------------------------------------------------------- #
# Git push
# --------------------------------------------------------------------------- #

def git_push(source_name: str) -> None:
    run_at = now_adelaide().strftime("%Y-%m-%d %H:%M ACST")
    cmds = [
        ["git", "add", "public/index.html"],
        ["git", "commit", "-m", f"data: {run_at} [{source_name}]"],
        ["git", "push", "origin", "main"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            # "nothing to commit" is fine — not an error
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print("No changes to commit.", file=sys.stderr)
                return
            print(f"git stderr: {result.stderr.strip()}", file=sys.stderr)
            raise RuntimeError(f"git failed: {' '.join(cmd)}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    state = load_state()
    source = pick_source(state.get("last_source"))
    print(f"Source: {source.DISPLAY_NAME} (last: {state.get('last_source', 'none')})", file=sys.stderr)

    scraped_at = now_adelaide()

    try:
        price_rows, no_price_stations = source.fetch_and_normalise()

        price_rows.sort(key=lambda r: (r["fuel_type"], route_index(r["town"]), r["price"]))
        no_price_stations.sort(key=lambda s: (route_index(s["town"]), s["name"]))

        print(
            f"Price rows: {len(price_rows)}, No-price stations: {len(no_price_stations)}",
            file=sys.stderr,
        )

        html = render_html(price_rows, no_price_stations, scraped_at, source.DISPLAY_NAME)
        OUTPUT_FILE.parent.mkdir(exist_ok=True)
        OUTPUT_FILE.write_text(html, encoding="utf-8")

        state["last_source"] = source.SOURCE_NAME
        state["last_run"] = scraped_at.isoformat()
        save_state(state)

        git_push(source.SOURCE_NAME)
        print(f"Done. → {OUTPUT_FILE}", file=sys.stderr)

    except Exception as exc:
        print(f"ERROR ({source.SOURCE_NAME}): {exc}", file=sys.stderr)
        # Only write error page if there's no existing output (avoids overwriting good data)
        if not OUTPUT_FILE.exists():
            error_html = render_error_html(str(exc), scraped_at)
            OUTPUT_FILE.parent.mkdir(exist_ok=True)
            OUTPUT_FILE.write_text(error_html, encoding="utf-8")
        sys.exit(1)


if __name__ == "__main__":
    main()
