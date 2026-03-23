"""FuelSnoop Supabase API source.

Uses the public Supabase anon key embedded in FuelSnoop's frontend.
The anon role is intentionally public and safe to use directly.
Token expiry: 2033-11-28.
"""
from __future__ import annotations

import httpx

from scrape.common import extract_town, is_stale, parse_updated, station_matches_target

SOURCE_NAME = "fuelsnoop"
DISPLAY_NAME = "FuelSnoop"

API_URL = "https://jqdyvthpvgnvlojefpav.supabase.co/rest/v1/rpc/sites_in_view"
_ANON = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxZHl2dGhwdmdu"
    "dmxvamVmcGF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDEwODM2MzksImV4cCI6MjAxNjY1OTYzOX0"
    ".7fEHEq5g3OFLBSyzuOObdJLZNlqFyVJPoYre2fYzN0E"
)

API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.fuelsnoop.com.au/",
    "apikey": _ANON,
    "Authorization": f"Bearer {_ANON}",
    "content-profile": "public",
    "x-client-info": "supabase-ssr/0.0.10",
    "Origin": "https://www.fuelsnoop.com.au",
}

API_BODY = {
    "min_lng": 138.70,
    "min_lat": -34.85,
    "max_lng": 140.80,
    "max_lat": -34.00,
    "brand_names": [],
}

FUEL_KEYS = {
    "Diesel": ["DSL", "dsl", "DL", "DIESEL"],
    "Premium Diesel": ["PDSL", "pdsl", "PDL", "PREMIUM_DIESEL"],
}


def _raw_stations() -> list[dict]:
    with httpx.Client(timeout=30) as client:
        resp = client.post(API_URL, json=API_BODY, headers=API_HEADERS)
        resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def fetch_and_normalise() -> tuple[list[dict], list[dict]]:
    """Returns (price_rows, no_price_stations)."""
    stations = _raw_stations()
    price_rows: list[dict] = []
    no_price_stations: list[dict] = []

    for station in stations:
        # FuelSnoop uses site_name / brand_name field names
        name = station.get("site_name") or station.get("name", "Unknown")
        brand = station.get("brand_name") or station.get("brand", "")
        address = station.get("address", "")

        # Build a normalised dict for matching (suburb from address if needed)
        match_dict = {"name": name, "address": address, "suburb": station.get("suburb", "")}
        if not station_matches_target(match_dict):
            continue

        town = extract_town(match_dict)
        prices = station.get("prices", {})
        found = False

        for fuel_label, keys in FUEL_KEYS.items():
            price = None
            updated_dt = None

            if isinstance(prices, dict):
                for key in keys:
                    if key not in prices:
                        continue
                    val = prices[key]
                    if isinstance(val, (int, float)):
                        price = float(val)
                    elif isinstance(val, dict):
                        amt = val.get("price") or val.get("amount") or val.get("value")
                        if amt is not None:
                            price = float(amt)
                        ts_raw = (
                            val.get("updated") or val.get("last_updated")
                            or val.get("updated_at") or val.get("lastUpdated")
                        )
                        updated_dt = parse_updated(ts_raw)
                    if price is not None:
                        break

            if price is not None:
                found = True
                price_rows.append({
                    "name": name,
                    "brand": brand,
                    "town": town,
                    "fuel_type": fuel_label,
                    "price": price,
                    "updated_dt": updated_dt,
                    "stale": is_stale(updated_dt),
                })

        if not found:
            no_price_stations.append({
                "name": name, "brand": brand, "town": town, "address": address,
            })

    return price_rows, no_price_stations
