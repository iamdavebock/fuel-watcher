"""Rich formatting helpers for fuel-watcher."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Braille sparkline chars — 8 levels
_SPARKS = " ▁▂▃▄▅▆▇█"

PRIORITY_FUELS = {"U91", "ULP", "E10", "Diesel", "DSL", "U98", "P98", "U95", "P95"}


def _age_str(ts: str | None) -> str:
    """Return human-friendly age of a timestamp."""
    if not ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        minutes = int((now - dt).total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except (ValueError, TypeError):
        return str(ts)


def _price_str(price: float | None) -> Text:
    if price is None:
        return Text("UNAVAIL", style="bold red")
    return Text(f"{price:.1f}", style="default")


def no_token_panel() -> None:
    console.print(
        Panel(
            "[bold yellow]API token not configured.[/bold yellow]\n\n"
            "Register at [link=https://fuelprice.io/api/]https://fuelprice.io/api/[/link] "
            "to obtain your free API token.\n\n"
            "Then add it to [cyan].env[/cyan]:\n"
            "[dim]FUELPRICE_API_TOKEN=your_token_here[/dim]",
            title="[red]No Token[/red]",
            border_style="red",
            expand=False,
        )
    )


def invalid_token_panel() -> None:
    console.print(
        Panel(
            "[bold red]API token was rejected (HTTP 401).[/bold red]\n\n"
            "Check the token in [cyan].env[/cyan] matches what was issued at "
            "[link=https://fuelprice.io/api/]https://fuelprice.io/api/[/link].",
            title="[red]Auth Error[/red]",
            border_style="red",
            expand=False,
        )
    )


def rate_limit_panel(msg: str) -> None:
    console.print(
        Panel(
            f"[yellow]{msg}[/yellow]",
            title="[yellow]Rate Limited[/yellow]",
            border_style="yellow",
            expand=False,
        )
    )


# --------------------------------------------------------------------------- #
# check / stations table
# --------------------------------------------------------------------------- #

def _extract_prices(station: dict) -> list[dict]:
    """Normalise price records out of a station object."""
    prices = station.get("prices") or station.get("fuel_prices") or []
    if isinstance(prices, dict):
        prices = list(prices.values())
    return prices


def stations_table(stations: list[dict], location: str) -> None:
    if not stations:
        console.print(f"[yellow]No stations found for '{location}'.[/yellow]")
        return

    table = Table(
        title=f"Stations — {location}",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Address")
    table.add_column("Suburb")
    table.add_column("Fuel Types")

    for s in stations:
        prices = _extract_prices(s)
        fuel_types = sorted({p.get("fuel_type") or p.get("type") or "" for p in prices} - {""})
        table.add_row(
            str(s.get("id") or s.get("station_id") or ""),
            s.get("name") or s.get("station_name") or "—",
            s.get("address") or "—",
            s.get("suburb") or s.get("city") or "—",
            ", ".join(fuel_types) if fuel_types else "—",
        )

    console.print(table)
    console.print(f"[dim]{len(stations)} station(s) found.[/dim]")


def prices_table(stations: list[dict], location: str, fuel_filter: str | None = None) -> dict[str, list[float]]:
    """
    Render a Rich prices table. Returns {fuel_type: [prices]} for diff tracking.
    """
    # Flatten all prices
    rows: list[dict] = []
    for s in stations:
        prices = _extract_prices(s)
        for p in prices:
            ft = p.get("fuel_type") or p.get("type") or "Unknown"
            if fuel_filter and ft.upper() != fuel_filter.upper():
                continue
            rows.append(
                {
                    "station_id": s.get("id") or s.get("station_id"),
                    "station": s.get("name") or s.get("station_name") or "Unknown",
                    "fuel_type": ft,
                    "price": p.get("price") or p.get("amount"),
                    "updated": p.get("last_updated") or p.get("updated_at") or p.get("timestamp"),
                }
            )

    if not rows:
        console.print(f"[yellow]No price data found for '{location}'.[/yellow]")
        return {}

    # Find cheapest per fuel type
    prices_by_type: dict[str, list[float]] = {}
    for r in rows:
        if r["price"] is not None:
            prices_by_type.setdefault(r["fuel_type"], []).append(float(r["price"]))

    cheapest: dict[str, float] = {ft: min(ps) for ft, ps in prices_by_type.items()}

    # Sort rows: priority fuels first, then alpha; within type sort by price
    def sort_key(r: dict) -> tuple:
        ft = r["fuel_type"]
        priority = 0 if any(ft.upper() == pf.upper() for pf in PRIORITY_FUELS) else 1
        price = r["price"] if r["price"] is not None else 9999.0
        return (priority, ft, price)

    rows.sort(key=sort_key)

    table = Table(
        title=f"Fuel Prices — {location}",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Station", min_width=20)
    table.add_column("Fuel Type", no_wrap=True)
    table.add_column("Price (c/L)", justify="right", no_wrap=True)
    table.add_column("Last Updated", style="dim", no_wrap=True)

    for r in rows:
        ft = r["fuel_type"]
        price_val = r["price"]
        is_cheapest = price_val is not None and float(price_val) == cheapest.get(ft)

        price_text = _price_str(float(price_val) if price_val is not None else None)
        if is_cheapest and price_val is not None:
            price_text = Text(f"{float(price_val):.1f} *", style="bold green")

        table.add_row(
            r["station"],
            ft,
            price_text,
            _age_str(r["updated"]),
        )

    console.print(table)
    console.print("[dim]* = cheapest in category[/dim]")
    return prices_by_type


# --------------------------------------------------------------------------- #
# watch diff display
# --------------------------------------------------------------------------- #

def watch_diff_table(
    stations: list[dict],
    location: str,
    prev_prices: dict[str, list[float]],
    fuel_filter: str | None = None,
) -> dict[str, list[float]]:
    """Like prices_table but includes a change indicator."""
    rows: list[dict] = []
    for s in stations:
        prices = _extract_prices(s)
        for p in prices:
            ft = p.get("fuel_type") or p.get("type") or "Unknown"
            if fuel_filter and ft.upper() != fuel_filter.upper():
                continue
            price_val = p.get("price") or p.get("amount")
            rows.append(
                {
                    "station": s.get("name") or s.get("station_name") or "Unknown",
                    "fuel_type": ft,
                    "price": price_val,
                    "updated": p.get("last_updated") or p.get("updated_at") or p.get("timestamp"),
                }
            )

    if not rows:
        console.print(f"[yellow]No price data for '{location}'.[/yellow]")
        return {}

    prices_by_type: dict[str, list[float]] = {}
    for r in rows:
        if r["price"] is not None:
            prices_by_type.setdefault(r["fuel_type"], []).append(float(r["price"]))

    cheapest: dict[str, float] = {ft: min(ps) for ft, ps in prices_by_type.items()}
    prev_cheapest: dict[str, float] = {ft: min(ps) for ft, ps in prev_prices.items() if ps}

    def sort_key(r: dict) -> tuple:
        ft = r["fuel_type"]
        priority = 0 if any(ft.upper() == pf.upper() for pf in PRIORITY_FUELS) else 1
        price = r["price"] if r["price"] is not None else 9999.0
        return (priority, ft, price)

    rows.sort(key=sort_key)

    table = Table(
        title=f"Fuel Prices — {location} (updated {datetime.now().strftime('%H:%M:%S')})",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Station", min_width=20)
    table.add_column("Fuel Type", no_wrap=True)
    table.add_column("Price (c/L)", justify="right", no_wrap=True)
    table.add_column("Change", justify="center", no_wrap=True)
    table.add_column("Last Updated", style="dim", no_wrap=True)

    for r in rows:
        ft = r["fuel_type"]
        price_val = r["price"]
        is_cheapest = price_val is not None and float(price_val) == cheapest.get(ft)

        if price_val is None:
            price_text = Text("UNAVAIL", style="bold red")
            change_text = Text("—", style="dim")
        else:
            pv = float(price_val)
            if is_cheapest:
                price_text = Text(f"{pv:.1f} *", style="bold green")
            else:
                price_text = Text(f"{pv:.1f}")

            prev_cheap = prev_cheapest.get(ft)
            if prev_cheap is None:
                change_text = Text("new", style="dim")
            elif pv < prev_cheap:
                change_text = Text(f"▼ {prev_cheap - pv:.1f}", style="bold green")
            elif pv > prev_cheap:
                change_text = Text(f"▲ {pv - prev_cheap:.1f}", style="bold red")
            else:
                change_text = Text("—", style="dim")

        table.add_row(
            r["station"],
            ft,
            price_text,
            change_text,
            _age_str(r["updated"]),
        )

    console.print(table)
    console.print("[dim]* = cheapest in category[/dim]")
    return prices_by_type


# --------------------------------------------------------------------------- #
# history sparkline
# --------------------------------------------------------------------------- #

def _sparkline(values: list[float], width: int = 40) -> str:
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1.0
    chars = []
    for v in values[-width:]:
        idx = int((v - mn) / rng * (len(_SPARKS) - 1))
        chars.append(_SPARKS[idx])
    return "".join(chars)


def history_panel(history: list[dict], station_id: str, fuel_type: str) -> None:
    # Extract price/timestamp pairs
    points: list[tuple[datetime, float]] = []
    for h in history:
        ts_raw = h.get("timestamp") or h.get("updated_at") or h.get("created_at")
        price_raw = h.get("price") or h.get("amount")
        if ts_raw is None or price_raw is None:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            points.append((ts, float(price_raw)))
        except (ValueError, TypeError):
            continue

    if not points:
        console.print(f"[yellow]No history data for station {station_id} / {fuel_type}.[/yellow]")
        return

    points.sort(key=lambda x: x[0])
    values = [p[1] for p in points]

    mn = min(values)
    mx = max(values)
    avg = statistics.mean(values)
    current = values[-1]
    spark = _sparkline(values)

    # Summary panel
    summary = (
        f"[bold]Station:[/bold] {station_id}   "
        f"[bold]Fuel:[/bold] {fuel_type}   "
        f"[bold]Points:[/bold] {len(values)}\n\n"
        f"[bold cyan]Current:[/bold cyan] {current:.1f} c/L   "
        f"[bold green]Min:[/bold green] {mn:.1f}   "
        f"[bold red]Max:[/bold red] {mx:.1f}   "
        f"[bold]Avg:[/bold] {avg:.1f}\n\n"
        f"[dim]Trend (oldest → newest):[/dim]\n"
        f"[bold]{spark}[/bold]\n\n"
        f"[dim]{points[0][0].strftime('%d %b %H:%M')} → {points[-1][0].strftime('%d %b %H:%M')}[/dim]"
    )

    console.print(
        Panel(
            summary,
            title=f"[cyan]Price History — {fuel_type}[/cyan]",
            border_style="cyan",
            expand=False,
        )
    )
