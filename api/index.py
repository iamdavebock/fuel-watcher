"""
fuel-watcher — Vercel serverless handler.
Fetches diesel + premium diesel prices from PetrolSpy and returns HTML.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler
from zoneinfo import ZoneInfo

import httpx

ADELAIDE_TZ = ZoneInfo("Australia/Adelaide")

API_URL = "https://petrolspy.com.au/webservice-1/station/box"
API_PARAMS = {
    "neLat": "-34.00",
    "neLng": "140.80",
    "swLat": "-34.85",
    "swLng": "138.70",
    # No fuelType filter — we parse DL + PDL from full response
}
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; fuel-watcher/1.0)",
    "Accept": "application/json",
    "Referer": "https://petrolspy.com.au/",
}

TARGET_TOWNS = [
    "gawler", "nuriootpa", "angaston", "tanunda", "truro", "blanchetown",
    "waikerie", "barmera", "berri", "glossop", "monash", "renmark",
    "paringa", "loxton", "roseworthy", "kapunda", "freeling",
    "kingston on murray", "cadell", "moorook", "cobdogla",
]

# Keys to try per fuel type in the prices dict
FUEL_KEYS = {
    "Diesel": ["DIESEL", "DL", "dl", "diesel"],
    "Premium Diesel": ["PREMIUM_DIESEL", "PDL", "pdl", "premium_diesel", "PREM_DIESEL", "prem_diesel"],
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def now_adelaide() -> datetime:
    return datetime.now(tz=ADELAIDE_TZ)


def format_timestamp(dt: datetime) -> str:
    return dt.strftime("%A %-d %b %Y, %-I:%M%p %Z").replace("AM", "am").replace("PM", "pm")


def station_matches_target(station: dict) -> bool:
    haystack = " ".join([
        station.get("name", ""),
        station.get("address", ""),
        station.get("suburb", ""),
    ]).lower()
    return any(town in haystack for town in TARGET_TOWNS)


def extract_town(station: dict) -> str:
    suburb = station.get("suburb", "").strip()
    if suburb:
        return suburb.title()
    address = station.get("address", "")
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


def parse_updated(updated_val) -> datetime | None:
    if updated_val is None:
        return None
    if isinstance(updated_val, (int, float)):
        try:
            return datetime.fromtimestamp(updated_val / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
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


# --------------------------------------------------------------------------- #
# Data fetching
# --------------------------------------------------------------------------- #

def fetch_stations() -> list[dict]:
    print("Fetching from PetrolSpy...", file=sys.stderr)
    with httpx.Client(timeout=30) as client:
        resp = client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
        resp.raise_for_status()

    data = resp.json()
    print(f"HTTP {resp.status_code} — keys: {list(data.keys())}", file=sys.stderr)

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
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                station_list = v
                break

    print(f"Total stations: {len(station_list)}", file=sys.stderr)
    return station_list


def build_rows(station_list: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Returns (price_rows, no_price_stations).
    price_rows: one entry per (station, fuel_type) with a price — DL and PDL only.
    no_price_stations: corridor stations with no diesel or premium diesel price.
    """
    price_rows: list[dict] = []
    no_price_stations: list[dict] = []

    for station in station_list:
        if not station_matches_target(station):
            continue

        prices = station.get("prices", {})
        found_any = False

        for fuel_label, keys in FUEL_KEYS.items():
            dl_price = None
            updated_dt = None

            if isinstance(prices, dict):
                dl = None
                for k in keys:
                    if k in prices:
                        dl = prices[k]
                        break

                if isinstance(dl, dict):
                    amount = dl.get("amount") or dl.get("price") or dl.get("value")
                    updated_val = dl.get("updated") or dl.get("lastUpdated") or dl.get("date")
                    if amount is not None:
                        try:
                            dl_price = float(amount)
                        except (ValueError, TypeError):
                            pass
                    updated_dt = parse_updated(updated_val)
                elif isinstance(dl, (int, float)):
                    dl_price = float(dl)

            # Top-level price fallback (only for Diesel, first pass)
            if dl_price is None and fuel_label == "Diesel":
                for key in ("price", "fuelPrice", "amount"):
                    if key in station:
                        try:
                            dl_price = float(station[key])
                            break
                        except (ValueError, TypeError):
                            pass

            if dl_price is not None:
                found_any = True
                price_rows.append({
                    "name": station.get("name", "Unknown"),
                    "brand": station.get("brand", ""),
                    "town": extract_town(station),
                    "fuel_type": fuel_label,
                    "price": dl_price,
                    "updated_dt": updated_dt,
                    "stale": is_stale(updated_dt),
                })

        if not found_any:
            no_price_stations.append({
                "name": station.get("name", "Unknown"),
                "brand": station.get("brand", ""),
                "town": extract_town(station),
                "address": station.get("address", ""),
            })

    price_rows.sort(key=lambda r: (r["fuel_type"], r["price"]))
    no_price_stations.sort(key=lambda r: (r["town"], r["name"]))
    return price_rows, no_price_stations


# --------------------------------------------------------------------------- #
# HTML rendering
# --------------------------------------------------------------------------- #

def _price_table_html(rows: list[dict], fuel_type: str) -> str:
    filtered = [r for r in rows if r["fuel_type"] == fuel_type]
    if not filtered:
        return ""

    cheapest_price = min(r["price"] for r in filtered)
    table_rows: list[str] = []

    for i, row in enumerate(filtered):
        is_cheapest = row["price"] == cheapest_price
        price_str = f"{row['price']:.1f}"
        updated_str = format_updated_display(row["updated_dt"])
        stale_badge = ' <span class="badge-stale">Stale</span>' if row["stale"] else ""
        brand_span = f' <span class="brand">{escape(row["brand"])}</span>' if row["brand"] else ""

        if is_cheapest:
            row_class = "row-cheapest"
            price_html = f'<span class="price-pill price-best">{escape(price_str)}c</span>'
        else:
            row_class = "row-alt" if i % 2 == 1 else "row-main"
            price_html = f'<span class="price-pill">{escape(price_str)}c</span>'

        table_rows.append(f"""
      <tr class="{row_class}">
        <td>{escape(row["name"])}{brand_span}</td>
        <td>{escape(row["town"])}</td>
        <td class="price-cell">{price_html}</td>
        <td class="updated-cell">{escape(updated_str)}{stale_badge}</td>
      </tr>""")

    rows_html = "\n".join(table_rows)
    cheapest_note = f'<p class="cheapest-note">Cheapest: <strong>{cheapest_price:.1f}c/L</strong> — {escape(filtered[0]["name"])}, {escape(filtered[0]["town"])}</p>'

    return f"""
  <section>
    <h2 class="section-title">{escape(fuel_type)}</h2>
    {cheapest_note}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Station</th>
            <th>Town</th>
            <th>c/L</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </section>"""


def _no_price_html(stations: list[dict]) -> str:
    if not stations:
        return ""

    station_items = "\n".join(
        f'<li><span class="no-price-name">{escape(s["name"])}</span>'
        f'{f" <span class=\'brand\'>{escape(s[\"brand\"])}</span>" if s["brand"] else ""}'
        f' — <span class="no-price-town">{escape(s["town"])}</span></li>'
        for s in stations
    )

    return f"""
  <section class="section-no-price">
    <h2 class="section-title section-title-warn">No Diesel Price Reported</h2>
    <p class="no-price-note">
      These stations are in the corridor but have no diesel or premium diesel price on PetrolSpy.
      Under SA law, stations must report price changes and unavailability within 30&nbsp;minutes —
      <strong>no price may indicate out of stock.</strong>
    </p>
    <ul class="no-price-list">
      {station_items}
    </ul>
  </section>"""


def render_html(price_rows: list[dict], no_price_stations: list[dict], scraped_at: datetime) -> str:
    timestamp_str = format_timestamp(scraped_at)
    diesel_html = _price_table_html(price_rows, "Diesel")
    premium_html = _price_table_html(price_rows, "Premium Diesel")
    no_price_section = _no_price_html(no_price_stations)

    if not price_rows and not no_price_stations:
        main_content = '<p class="no-data">No data available for this corridor.</p>'
    else:
        main_content = diesel_html + premium_html + no_price_section

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SA Diesel Prices — Gawler to Renmark</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&display=swap" rel="stylesheet">
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
      --red:       #ef4444;
      --red-bg:    #1f0a0a;
      --red-border:#7f1d1d;
      --radius:    8px;
    }}

    body {{
      font-family: 'DM Sans', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 1rem;
    }}

    .container {{ max-width: 860px; margin: 0 auto; }}

    header {{
      padding: 2rem 0 1.5rem;
      border-bottom: 1px solid var(--bg-mid);
      margin-bottom: 2rem;
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

    section {{ margin-bottom: 2.5rem; }}

    .section-title {{
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--teal);
      margin-bottom: 0.6rem;
      letter-spacing: -0.2px;
    }}
    .section-title-warn {{ color: var(--orange); }}

    .cheapest-note {{
      font-size: 0.9rem;
      color: var(--text-dim);
      margin-bottom: 0.75rem;
    }}
    .cheapest-note strong {{ color: var(--text); }}

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
    thead tr {{ background: var(--teal); }}
    thead th {{
      color: #fff;
      font-weight: 600;
      text-align: left;
      padding: 0.7rem 1rem;
      white-space: nowrap;
    }}
    tbody tr {{
      border-bottom: 1px solid rgba(255,255,255,0.04);
      transition: background 0.15s;
    }}
    tbody tr:hover {{ background: var(--teal-glow) !important; }}
    tr.row-main     {{ background: var(--bg-alt); }}
    tr.row-alt      {{ background: var(--bg-mid); }}
    tr.row-cheapest {{
      background: var(--bg-alt);
      border-left: 3px solid var(--teal);
    }}
    td {{
      padding: 0.6rem 1rem;
      vertical-align: middle;
    }}
    .brand {{
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-left: 0.35rem;
    }}
    .price-cell {{ white-space: nowrap; }}
    .price-pill {{
      display: inline-block;
      background: var(--teal-dim);
      color: #fff;
      font-size: 1rem;
      font-weight: 700;
      padding: 0.18rem 0.6rem;
      border-radius: 999px;
      letter-spacing: -0.3px;
    }}
    .price-best {{
      background: var(--teal);
      font-size: 1.05rem;
    }}
    .updated-cell {{
      font-size: 0.83rem;
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

    /* Out of fuel / no price section */
    .section-no-price {{
      background: var(--red-bg);
      border: 1px solid var(--red-border);
      border-radius: var(--radius);
      padding: 1.25rem 1.5rem;
    }}
    .no-price-note {{
      font-size: 0.88rem;
      color: var(--text-dim);
      margin-bottom: 1rem;
      line-height: 1.6;
    }}
    .no-price-note strong {{ color: var(--orange); }}
    .no-price-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }}
    .no-price-list li {{
      font-size: 0.95rem;
      padding: 0.45rem 0.75rem;
      background: rgba(239,68,68,0.08);
      border-radius: 6px;
      border-left: 3px solid var(--red);
    }}
    .no-price-name {{ font-weight: 600; }}
    .no-price-town {{ color: var(--text-dim); }}

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
      td, th {{ padding: 0.5rem 0.65rem; }}
      .price-pill {{ font-size: 0.9rem; }}
      .section-no-price {{ padding: 1rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>SA Diesel Prices</h1>
      <div class="subtitle">Gawler &rarr; Renmark &middot; Riverland corridor</div>
      <div class="meta">
        <span>Last updated: {escape(timestamp_str)}</span>
        <span class="badge-source">Data: PetrolSpy</span>
      </div>
    </header>

    <main>
      {main_content}
    </main>

    <footer>
      <div>fuel.davebock.au &middot; Prices sourced from community reports. Verify at the bowser.</div>
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


# --------------------------------------------------------------------------- #
# Vercel handler
# --------------------------------------------------------------------------- #

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        scraped_at = now_adelaide()
        try:
            station_list = fetch_stations()
            price_rows, no_price_stations = build_rows(station_list)
            print(f"Price rows: {len(price_rows)}, No-price stations: {len(no_price_stations)}", file=sys.stderr)
            html = render_html(price_rows, no_price_stations, scraped_at)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            html = render_error_html(str(exc), scraped_at)

        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # suppress default access log
