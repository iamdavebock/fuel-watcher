"""Click CLI entry point for fuel-watcher."""

from __future__ import annotations

import sys
import time

import click
from rich.console import Console

from . import api
from . import display

console = Console()

DEFAULT_LOCATION = "Renmark"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 5


def _handle_api_errors(fn):
    """Decorator that converts API exceptions into user-friendly output and exits."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except api.AuthError as e:
            if "no_token" in str(e):
                display.no_token_panel()
            else:
                display.invalid_token_panel()
            sys.exit(1)
        except api.RateLimitError as e:
            display.rate_limit_panel(str(e))
            sys.exit(1)
        except api.APIError as e:
            console.print(f"[red]API error:[/red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            sys.exit(1)

    return wrapper


@click.group()
@click.version_option()
def cli():
    """fuel-watcher — SA fuel price monitor.

    Tracks fuel prices in South Australia, focused on the Renmark / Riverland region.

    \b
    Examples:
      fuel check
      fuel check --location "Port Augusta"
      fuel stations
      fuel watch --interval 15 --fuel-type U91
      fuel history --station 1234 --fuel-type Diesel --hours 72
    """


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #

@cli.command()
@click.option(
    "--location", "-l",
    default=DEFAULT_LOCATION,
    show_default=True,
    help="Location name to search (city or suburb).",
)
@click.option(
    "--fuel-type", "-f",
    default=None,
    help="Filter to a specific fuel type (e.g. U91, Diesel).",
)
@click.option(
    "--refresh", is_flag=True, default=False,
    help="Bust the station cache and re-fetch from API.",
)
@_handle_api_errors
def check(location: str, fuel_type: str | None, refresh: bool):
    """Show current fuel prices for a location.

    Fetches all stations in LOCATION and displays a table of prices.
    The cheapest price per fuel type is highlighted in green.

    \b
    Examples:
      fuel check
      fuel check --location Renmark
      fuel check --fuel-type Diesel
      fuel check --refresh
    """
    if refresh:
        api.bust_location_cache(location)

    with console.status(f"Fetching stations for {location}..."):
        stations = api.get_stations(location)

    if not stations:
        console.print(f"[yellow]No stations found for '{location}'.[/yellow]")
        console.print("[dim]Try --refresh to bypass cache, or check the location name.[/dim]")
        return

    # Fetch individual station details to get current prices
    detailed: list[dict] = []
    with console.status(f"Fetching prices ({len(stations)} stations)..."):
        for s in stations:
            sid = s.get("id") or s.get("station_id")
            if sid:
                try:
                    detail = api.get_station(str(sid))
                    # Merge base info with detail
                    merged = {**s, **detail}
                    detailed.append(merged)
                except (api.APIError, Exception):
                    # Fall back to whatever the stations list gave us
                    detailed.append(s)
            else:
                detailed.append(s)

    display.prices_table(detailed, location, fuel_filter=fuel_type)


# --------------------------------------------------------------------------- #
# watch
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--location", "-l", default=DEFAULT_LOCATION, show_default=True)
@click.option(
    "--interval", "-i",
    default=DEFAULT_INTERVAL,
    show_default=True,
    type=click.IntRange(MIN_INTERVAL, 3600),
    help=f"Poll interval in minutes (min {MIN_INTERVAL}).",
)
@click.option("--fuel-type", "-f", default=None, help="Filter to a specific fuel type.")
@_handle_api_errors
def watch(location: str, interval: int, fuel_type: str | None):
    """Poll fuel prices on an interval and show changes.

    Fetches prices every INTERVAL minutes and highlights price movements.
    Press Ctrl+C to stop.

    \b
    Examples:
      fuel watch
      fuel watch --interval 15
      fuel watch --fuel-type U91
      fuel watch --location "Berri" --interval 60
    """
    console.print(
        f"[bold cyan]Watching[/bold cyan] {location} "
        f"every [bold]{interval}[/bold] min"
        + (f" — [bold]{fuel_type}[/bold] only" if fuel_type else "")
        + " — [dim]Ctrl+C to stop[/dim]"
    )

    prev_prices: dict[str, list[float]] = {}

    def fetch_and_display() -> dict[str, list[float]]:
        stations = api.get_stations(location)
        detailed: list[dict] = []
        for s in stations:
            sid = s.get("id") or s.get("station_id")
            if sid:
                try:
                    detail = api.get_station(str(sid))
                    detailed.append({**s, **detail})
                except Exception:
                    detailed.append(s)
            else:
                detailed.append(s)

        if prev_prices:
            return display.watch_diff_table(
                detailed, location, prev_prices, fuel_filter=fuel_type
            )
        return display.prices_table(detailed, location, fuel_filter=fuel_type)

    try:
        while True:
            prev_prices = fetch_and_display() or prev_prices
            console.print(
                f"[dim]Next update in {interval} min. Ctrl+C to stop.[/dim]"
            )
            time.sleep(interval * 60)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--station", "-s", required=True, help="Station ID (from `fuel stations`).")
@click.option("--fuel-type", "-f", default="U91", show_default=True, help="Fuel type to display.")
@click.option(
    "--hours", "-h",
    default=48,
    show_default=True,
    type=click.IntRange(1, 720),
    help="Hours of history to fetch.",
)
@_handle_api_errors
def history(station: str, fuel_type: str, hours: int):
    """Show price history for a station as a sparkline.

    Displays a braille sparkline and min/max/average summary.

    \b
    Examples:
      fuel history --station 1234
      fuel history --station 1234 --fuel-type Diesel --hours 72
    """
    with console.status(f"Fetching {hours}h history for station {station}..."):
        hist = api.get_station_history(station, hours=hours)

    # Filter by fuel type if the history records include it
    filtered = [
        h for h in hist
        if (h.get("fuel_type") or h.get("type") or fuel_type).upper() == fuel_type.upper()
    ]
    if not filtered and hist:
        # History may not include fuel_type field — use all records
        filtered = hist

    display.history_panel(filtered, station, fuel_type)


# --------------------------------------------------------------------------- #
# stations
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--location", "-l", default=DEFAULT_LOCATION, show_default=True)
@click.option(
    "--refresh", is_flag=True, default=False,
    help="Bust the station cache and re-fetch from API.",
)
@_handle_api_errors
def stations(location: str, refresh: bool):
    """List all stations in a location.

    Shows station IDs, names, addresses and available fuel types.
    Use station IDs with `fuel history`.

    \b
    Examples:
      fuel stations
      fuel stations --location "Berri"
      fuel stations --refresh
    """
    if refresh:
        api.bust_location_cache(location)

    with console.status(f"Fetching stations for {location}..."):
        raw_stations = api.get_stations(location)

    display.stations_table(raw_stations, location)


if __name__ == "__main__":
    cli()
