"""HTML rendering for fuel-watcher static output."""
from __future__ import annotations

from datetime import datetime
from html import escape

from scrape.common import format_timestamp, format_updated_display, route_index


def _price_table_html(rows: list[dict], fuel_type: str) -> str:
    filtered = [r for r in rows if r["fuel_type"] == fuel_type]
    if not filtered:
        return ""

    cheapest_price = min(r["price"] for r in filtered)
    cheapest_row = min(filtered, key=lambda r: r["price"])
    filtered.sort(key=lambda r: (route_index(r["town"]), r["price"]))

    table_rows: list[str] = []
    prev_town = None

    for row in filtered:
        if row["town"] != prev_town:
            prev_town = row["town"]
            table_rows.append(
                f'<tr class="town-group"><td colspan="3">{escape(row["town"])}</td></tr>'
            )

        is_cheapest = row["price"] == cheapest_price
        price_str = f"{row['price']:.1f}"
        updated_str = format_updated_display(row["updated_dt"])
        stale_badge = ' <span class="badge-stale">Stale</span>' if row["stale"] else ""
        brand_span = f' <span class="brand">{escape(row["brand"])}</span>' if row["brand"] else ""
        price_html = (
            f'<span class="price-pill price-best">{escape(price_str)}c</span>'
            if is_cheapest
            else f'<span class="price-pill">{escape(price_str)}c</span>'
        )
        row_class = "row-cheapest" if is_cheapest else "row-main"

        table_rows.append(f"""
      <tr class="{row_class}">
        <td>{escape(row["name"])}{brand_span}</td>
        <td class="price-cell">{price_html}</td>
        <td class="updated-cell">{escape(updated_str)}{stale_badge}</td>
      </tr>""")

    rows_html = "\n".join(table_rows)
    cheapest_note = (
        f'<p class="cheapest-note">Cheapest on route: '
        f'<strong>{cheapest_price:.1f}c/L</strong> — '
        f'{escape(cheapest_row["name"])}, {escape(cheapest_row["town"])}</p>'
    )

    return f"""
  <section>
    <h2 class="section-title">{escape(fuel_type)}</h2>
    {cheapest_note}
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Station</th><th>c/L</th><th>Updated</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </section>"""


def _no_price_html(stations: list[dict]) -> str:
    if not stations:
        return ""

    sorted_stations = sorted(stations, key=lambda s: (route_index(s["town"]), s["name"]))
    items = []
    for s in sorted_stations:
        brand = f' <span class="brand">{escape(s["brand"])}</span>' if s["brand"] else ""
        items.append(
            f'<li><span class="no-price-town">{escape(s["town"])}</span>'
            f' — <span class="no-price-name">{escape(s["name"])}</span>{brand}</li>'
        )

    return f"""
  <section class="section-no-price">
    <h2 class="section-title section-title-warn">No Diesel Price Reported</h2>
    <p class="no-price-note">
      These corridor stations have no diesel or premium diesel price on record.
      Under SA law, stations must report unavailability within 30&nbsp;minutes —
      <strong>no price may indicate out of stock.</strong>
    </p>
    <ul class="no-price-list">{''.join(items)}</ul>
  </section>"""


def render_html(
    price_rows: list[dict],
    no_price_stations: list[dict],
    scraped_at: datetime,
    source_name: str,
) -> str:
    timestamp_str = format_timestamp(scraped_at)
    scraped_iso = scraped_at.isoformat()
    diesel_html = _price_table_html(price_rows, "Diesel")
    no_price_section = _no_price_html(no_price_stations)

    if not price_rows and not no_price_stations:
        main_content = '<p class="no-data">No data available for this corridor.</p>'
    else:
        main_content = diesel_html + no_price_section

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SA Diesel Prices — Gawler to Renmark</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0a0f1c; --bg-alt: #0d1629; --bg-mid: #111f33;
      --teal: #008080; --teal-dim: #006666; --teal-glow: rgba(0,128,128,0.12);
      --text: #e2e8f0; --text-dim: #94a3b8;
      --orange: #f59e0b; --red: #ef4444; --red-bg: #1f0a0a; --red-border: #7f1d1d;
      --radius: 8px;
    }}
    body {{ font-family: 'DM Sans', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; padding: 1rem; }}
    .container {{ max-width: 860px; margin: 0 auto; }}
    header {{ padding: 2rem 0 1.5rem; border-bottom: 1px solid var(--bg-mid); margin-bottom: 2rem; }}
    header h1 {{ font-size: clamp(1.6rem, 4vw, 2.2rem); font-weight: 700; color: #fff; letter-spacing: -0.5px; }}
    header .subtitle {{ color: var(--teal); font-size: 1rem; font-weight: 500; margin-top: 0.25rem; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin-top: 1rem; font-size: 0.85rem; color: var(--text-dim); }}
    .badge-source {{ background: var(--teal-dim); color: #fff; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }}
    section {{ margin-bottom: 2.5rem; }}
    .section-title {{ font-size: 1.15rem; font-weight: 700; color: var(--teal); margin-bottom: 0.6rem; letter-spacing: -0.2px; }}
    .section-title-warn {{ color: var(--orange); }}
    .cheapest-note {{ font-size: 0.9rem; color: var(--text-dim); margin-bottom: 0.75rem; }}
    .cheapest-note strong {{ color: var(--text); }}
    .table-wrap {{ overflow-x: auto; border-radius: var(--radius); border: 1px solid var(--bg-mid); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    thead tr {{ background: var(--teal); }}
    thead th {{ color: #fff; font-weight: 600; text-align: left; padding: 0.7rem 1rem; white-space: nowrap; }}
    tbody tr {{ border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.15s; }}
    tbody tr:hover {{ background: var(--teal-glow) !important; }}
    tr.row-main {{ background: var(--bg-alt); }}
    tr.row-cheapest {{ background: var(--bg-alt); border-left: 3px solid var(--teal); }}
    tr.town-group td {{ background: var(--bg-mid); color: var(--teal); font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 0.35rem 1rem; border-top: 1px solid rgba(0,128,128,0.2); }}
    td {{ padding: 0.6rem 1rem; vertical-align: middle; }}
    .brand {{ font-size: 0.78rem; color: var(--text-dim); margin-left: 0.35rem; }}
    .price-cell {{ white-space: nowrap; }}
    .price-pill {{ display: inline-block; background: var(--teal-dim); color: #fff; font-size: 1rem; font-weight: 700; padding: 0.18rem 0.6rem; border-radius: 999px; letter-spacing: -0.3px; }}
    .price-best {{ background: var(--teal); font-size: 1.05rem; }}
    .updated-cell {{ font-size: 0.83rem; color: var(--text-dim); white-space: nowrap; }}
    .badge-stale {{ display: inline-block; background: var(--orange); color: #000; font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 999px; margin-left: 0.4rem; vertical-align: middle; }}
    .section-no-price {{ background: var(--red-bg); border: 1px solid var(--red-border); border-radius: var(--radius); padding: 1.25rem 1.5rem; }}
    .no-price-note {{ font-size: 0.88rem; color: var(--text-dim); margin-bottom: 1rem; line-height: 1.6; }}
    .no-price-note strong {{ color: var(--orange); }}
    .no-price-list {{ list-style: none; display: flex; flex-direction: column; gap: 0.4rem; }}
    .no-price-list li {{ font-size: 0.95rem; padding: 0.45rem 0.75rem; background: rgba(239,68,68,0.08); border-radius: 6px; border-left: 3px solid var(--red); }}
    .no-price-name {{ font-weight: 600; }}
    .no-price-town {{ color: var(--text-dim); }}
    .no-data {{ padding: 2rem; color: var(--text-dim); text-align: center; }}
    footer {{ margin-top: 2rem; padding-top: 1.25rem; border-top: 1px solid var(--bg-mid); font-size: 0.8rem; color: var(--text-dim); line-height: 1.7; }}
    @media (max-width: 600px) {{ td, th {{ padding: 0.5rem 0.65rem; }} .price-pill {{ font-size: 0.9rem; }} .section-no-price {{ padding: 1rem; }} }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>SA Diesel Prices</h1>
      <div class="subtitle">Gawler &rarr; Renmark &middot; Riverland corridor</div>
      <div class="meta">
        <span>Scraped: {escape(timestamp_str)} &middot; <span id="time-ago"></span></span>
        <span class="badge-source">Data: {escape(source_name)}</span>
      </div>
    </header>
    <main>{main_content}</main>
    <footer>
      <div>fuel.davebock.au &middot; Prices sourced from community reports. Verify at the bowser.</div>
    </footer>
  </div>
  <script>
    var scraped = new Date("{scraped_iso}");
    function ago() {{
      var diff = Math.floor((Date.now() - scraped) / 1000);
      var s;
      if (diff < 60) s = diff + "s ago";
      else if (diff < 3600) s = Math.floor(diff/60) + "m ago";
      else s = Math.floor(diff/3600) + "h " + Math.floor((diff%3600)/60) + "m ago";
      document.getElementById("time-ago").textContent = s;
    }}
    ago();
    setInterval(ago, 30000);
  </script>
</body>
</html>"""


def render_error_html(error_msg: str, scraped_at: datetime) -> str:
    timestamp_str = format_timestamp(scraped_at)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SA Diesel Prices — Error</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&display=swap" rel="stylesheet">
  <style>body{{font-family:'DM Sans',sans-serif;background:#0a0f1c;color:#e2e8f0;padding:2rem}}.error{{background:#1f0a0a;border:1px solid #7f1d1d;border-radius:8px;padding:1.5rem;margin-top:2rem}}h1{{color:#fff}}.dim{{color:#94a3b8;font-size:.85rem;margin-top:.5rem}}pre{{margin-top:1rem;font-size:.82rem;white-space:pre-wrap;word-break:break-word;color:#fca5a5}}</style>
</head>
<body>
  <h1>SA Diesel Prices</h1>
  <div class="dim">Attempted: {escape(timestamp_str)}</div>
  <div class="error"><strong>Failed to retrieve price data.</strong><pre>{escape(str(error_msg))}</pre></div>
</body>
</html>"""
