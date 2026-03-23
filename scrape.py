"""
fuel-watcher scraper — fetches diesel prices from PetrolSpy and renders
a static HTML page at /var/www/fuel-watcher/index.html.

Runs as a cron job; all logging to stderr.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from html import escape
from zoneinfo import ZoneInfo

import httpx

ADELAIDE_TZ = ZoneInfo("Australia/Adelaide")

API_URL = "https://petrolspy.com.au/webservice-1/station/box"
API_PARAMS = {
    "neLat": "-34.00",
    "neLng": "140.80",
    "swLat": "-34.85",
    "swLng": "138.70",
    "fuelType": "DL",
}
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fuel-watcher/1.0)",
    "Accept": "application/json",
    "Referer": "https://petrolspy.com.au/",
}

OUTPUT_DIR = "/var/www/fuel-watcher"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

TARGET_TOWNS = [
    "gawler", "nuriootpa", "angaston", "tanunda", "truro", "blanchetown",
    "waikerie", "barmera", "berri", "glossop", "monash", "renmark",
    "paringa", "loxton", "roseworthy", "kapunda", "freeling",
    "kingston on murray", "cadell", "moorook", "cobdogla",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def now_adelaide() -> datetime:
    return datetime.now(tz=ADELAIDE_TZ)


def format_timestamp(dt: datetime) -> str:
    return dt.strftime("%A %-d %b %Y, %-I:%M%p %Z").replace("AM", "am").replace("PM", "pm")


def station_matches_target(station: dict) -> bool:
    """Return True if station suburb, address, or name contains a target town."""
    haystack = " ".join([
        station.get("name", ""),
        station.get("address", ""),
        station.get("suburb", ""),
    ]).lower()
    return any(town in haystack for town in TARGET_TOWNS)


def extract_town(station: dict) -> str:
    """Return suburb field if present, otherwise parse from address."""
    suburb = station.get("suburb", "").strip()
    if suburb:
        return suburb.title()
    address = station.get("address", "")
    # Address format: "123 Main St, Town SA 5000"
    parts = address.split(",")
    if len(parts) >= 2:
        town_part = parts[-1].strip()
        tokens = town_part.split()
        if len(tokens) >= 3 and tokens[-2].isupper() and tokens[-1].isdigit():
            return " ".join(tokens[:-2]).title()
        elif len(tokens) >= 2 and tokens[-1].isdigit():
            return " ".join(tokens[:-1]).title()
        return town_part.title()
    for town in TARGET_TOWNS:
        if town in address.lower():
            return town.title()
    return ""


def parse_updated(updated_val: str | int | float | None) -> datetime | None:
    if updated_val is None:
        return None
    # Unix timestamp in milliseconds (PetrolSpy uses this format)
    if isinstance(updated_val, (int, float)):
        try:
            return datetime.fromtimestamp(updated_val / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    # ISO string fallback
    try:
        dt = datetime.fromisoformat(str(updated_val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def is_stale(updated_dt: datetime | None) -> bool:
    if updated_dt is None:
        return True
    age = datetime.now(tz=timezone.utc) - updated_dt.astimezone(timezone.utc)
    return age > timedelta(hours=48)


def format_updated_display(updated_dt: datetime | None) -> str:
    if updated_dt is None:
        return "Unknown"
    local = updated_dt.astimezone(ADELAIDE_TZ)
    return local.strftime("%-d %b, %-I:%M%p").replace("AM", "am").replace("PM", "pm")


def fetch_stations() -> list[dict]:
    log("Fetching from PetrolSpy API...")
    with httpx.Client(timeout=30) as client:
        resp = client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
        resp.raise_for_status()

    raw = resp.text
    log(f"HTTP {resp.status_code} — {len(raw)} bytes received")

    # Dump raw response on stderr for debugging
    log("--- RAW RESPONSE (first 2000 chars) ---")
    log(raw[:2000])
    log("--- END RAW RESPONSE ---")

    data = resp.json()
    log(f"Top-level keys: {list(data.keys())}")

    # Navigate to station list — handle a few known shapes
    station_list: list[dict] = []
    if isinstance(data, list):
        station_list = data
    elif "message" in data:
        msg = data["message"]
        if isinstance(msg, dict) and "list" in msg:
            station_list = msg["list"]
        elif isinstance(msg, list):
            station_list = msg
    elif "list" in data:
        station_list = data["list"]
    elif "stations" in data:
        station_list = data["stations"]
    else:
        # Last resort: find first list value
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                station_list = v
                break

    log(f"Total stations in response: {len(station_list)}")
    return station_list


def build_rows(station_list: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for station in station_list:
        if not station_matches_target(station):
            continue

        # Extract price — handle nested or flat structures
        prices = station.get("prices", {})
        dl_price = None
        updated_dt = None

        if isinstance(prices, dict):
            # API query param is "DL" but response key is "DIESEL"
            dl = (
                prices.get("DIESEL")
                or prices.get("DL")
                or prices.get("dl")
                or prices.get("diesel")
            )
            if isinstance(dl, dict):
                amount = dl.get("amount") or dl.get("price") or dl.get("value")
                updated_val = dl.get("updated") or dl.get("lastUpdated") or dl.get("date")
                if amount is not None:
                    dl_price = float(amount)
                updated_dt = parse_updated(updated_val)
            elif isinstance(dl, (int, float)):
                dl_price = float(dl)
        elif isinstance(prices, (int, float)):
            dl_price = float(prices)

        # Also check top-level price fields
        if dl_price is None:
            for key in ("price", "fuelPrice", "amount"):
                if key in station:
                    try:
                        dl_price = float(station[key])
                        break
                    except (ValueError, TypeError):
                        pass

        if dl_price is None:
            continue  # Skip stations without a price

        rows.append({
            "name": station.get("name", "Unknown"),
            "brand": station.get("brand", ""),
            "address": station.get("address", ""),
            "town": extract_town(station),
            "price": dl_price,
            "updated_dt": updated_dt,
            "stale": is_stale(updated_dt),
        })

    rows.sort(key=lambda r: r["price"])
    return rows


def render_html(rows: list[dict], scraped_at: datetime) -> str:
    timestamp_str = format_timestamp(scraped_at)

    if not rows:
        body_content = '<p class="no-data">No diesel price data available for this corridor.</p>'
        table_html = body_content
    else:
        table_rows: list[str] = []
        for i, row in enumerate(rows):
            is_cheapest = i == 0
            price_str = f"{row['price']:.1f}"
            updated_str = format_updated_display(row["updated_dt"])
            stale_badge = (
                ' <span class="badge-stale">Stale</span>' if row["stale"] else ""
            )
            cheapest_class = ' class="row-cheapest"' if is_cheapest else ""
            row_class = "row-alt" if i % 2 == 1 else "row-main"
            if is_cheapest:
                row_class = "row-cheapest"

            table_rows.append(f"""
      <tr class="{row_class}"{cheapest_class}>
        <td>{escape(row["name"])}{f' <span class="brand">{escape(row["brand"])}</span>' if row["brand"] else ""}</td>
        <td>{escape(row["town"])}</td>
        <td class="price-cell"><span class="price-pill">{escape(price_str)}c</span></td>
        <td class="updated-cell">{escape(updated_str)}{stale_badge}</td>
      </tr>""")

        rows_html = "\n".join(table_rows)
        table_html = f"""
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Station</th>
          <th>Town</th>
          <th>Diesel (c/L)</th>
          <th>Last Updated</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SA Diesel Prices — Gawler to Renmark</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0a0f1c;
      --bg-alt:    #0d1629;
      --bg-mid:    #111f33;
      --teal:      #008080;
      --teal-dim:  #006666;
      --teal-glow: rgba(0,128,128,0.12);
      --text:      #e2e8f0;
      --text-dim:  #94a3b8;
      --orange:    #f59e0b;
      --radius:    8px;
    }}

    body {{
      font-family: 'DM Sans', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 1rem;
    }}

    .container {{
      max-width: 860px;
      margin: 0 auto;
    }}

    header {{
      padding: 2rem 0 1.5rem;
      border-bottom: 1px solid var(--bg-mid);
      margin-bottom: 1.5rem;
    }}

    header h1 {{
      font-size: clamp(1.6rem, 4vw, 2.2rem);
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.5px;
    }}

    header .subtitle {{
      color: var(--teal);
      font-size: 1rem;
      font-weight: 500;
      margin-top: 0.25rem;
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin-top: 1rem;
      font-size: 0.85rem;
      color: var(--text-dim);
    }}

    .badge-source {{
      background: var(--teal-dim);
      color: #fff;
      padding: 0.2rem 0.6rem;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
    }}

    .table-wrap {{
      overflow-x: auto;
      border-radius: var(--radius);
      border: 1px solid var(--bg-mid);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}

    thead tr {{
      background: var(--teal);
    }}

    thead th {{
      color: #fff;
      font-weight: 600;
      text-align: left;
      padding: 0.75rem 1rem;
      white-space: nowrap;
    }}

    tbody tr {{
      border-bottom: 1px solid rgba(255,255,255,0.04);
      transition: background 0.15s;
    }}

    tbody tr:hover {{
      background: var(--teal-glow) !important;
    }}

    tr.row-main  {{ background: var(--bg-alt); }}
    tr.row-alt   {{ background: var(--bg-mid); }}
    tr.row-cheapest {{
      background: var(--bg-alt);
      border-left: 3px solid var(--teal);
    }}

    td {{
      padding: 0.65rem 1rem;
      vertical-align: middle;
    }}

    .brand {{
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-left: 0.35rem;
    }}

    .price-cell {{
      white-space: nowrap;
    }}

    .price-pill {{
      display: inline-block;
      background: var(--teal);
      color: #fff;
      font-size: 1.05rem;
      font-weight: 700;
      padding: 0.2rem 0.65rem;
      border-radius: 999px;
      letter-spacing: -0.3px;
    }}

    .updated-cell {{
      font-size: 0.85rem;
      color: var(--text-dim);
      white-space: nowrap;
    }}

    .badge-stale {{
      display: inline-block;
      background: var(--orange);
      color: #000;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.1rem 0.45rem;
      border-radius: 999px;
      margin-left: 0.4rem;
      vertical-align: middle;
    }}

    .no-data {{
      padding: 2rem;
      color: var(--text-dim);
      text-align: center;
    }}

    footer {{
      margin-top: 2rem;
      padding-top: 1.25rem;
      border-top: 1px solid var(--bg-mid);
      font-size: 0.8rem;
      color: var(--text-dim);
      line-height: 1.7;
    }}

    @media (max-width: 600px) {{
      td, th {{ padding: 0.55rem 0.65rem; }}
      .price-pill {{ font-size: 0.95rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>SA Diesel Prices</h1>
      <div class="subtitle">Gawler &rarr; Renmark &middot; Riverland</div>
      <div class="meta">
        <span>Last scraped: {escape(timestamp_str)}</span>
        <span class="badge-source">Data: PetrolSpy</span>
      </div>
    </header>

    <main>
      {table_html}
    </main>

    <footer>
      <div>Updated automatically &middot; fuel.davebock.au</div>
      <div>Prices sourced from community reports. Verify at the bowser.</div>
    </footer>
  </div>
</body>
</html>"""


def render_error_html(error_msg: str, scraped_at: datetime) -> str:
    timestamp_str = format_timestamp(scraped_at)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SA Diesel Prices — Error</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'DM Sans', sans-serif; background: #0a0f1c; color: #e2e8f0; padding: 2rem; }}
    .error {{ background: #1f0a0a; border: 1px solid #7f1d1d; border-radius: 8px; padding: 1.5rem; margin-top: 2rem; }}
    h1 {{ color: #fff; }} .dim {{ color: #94a3b8; font-size: 0.85rem; margin-top: 0.5rem; }}
    pre {{ margin-top: 1rem; font-size: 0.82rem; white-space: pre-wrap; word-break: break-word; color: #fca5a5; }}
  </style>
</head>
<body>
  <h1>SA Diesel Prices</h1>
  <div class="dim">Attempted: {escape(timestamp_str)}</div>
  <div class="error">
    <strong>Failed to retrieve price data.</strong>
    <pre>{escape(str(error_msg))}</pre>
  </div>
</body>
</html>"""


def main() -> None:
    scraped_at = now_adelaide()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        station_list = fetch_stations()
        rows = build_rows(station_list)
        log(f"Stations matching corridor: {len(rows)}")
        if rows:
            log("Sample prices:")
            for r in rows[:5]:
                log(f"  {r['name']} ({r['town']}): {r['price']:.1f}c")
        html = render_html(rows, scraped_at)
    except Exception as exc:
        log(f"ERROR: {exc}")
        html = render_error_html(str(exc), scraped_at)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    log(f"Written: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
