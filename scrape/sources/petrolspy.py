"""PetrolSpy bounding box API source."""
from __future__ import annotations

import httpx

from scrape.common import extract_town, is_stale, parse_updated, station_matches_target

SOURCE_NAME = "petrolspy"
DISPLAY_NAME = "PetrolSpy"

API_URL = "https://petrolspy.com.au/webservice-1/station/box"
API_PARAMS = {
    "neLat": "-34.00",
    "neLng": "140.80",
    "swLat": "-34.85",
    "swLng": "138.70",
}
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://petrolspy.com.au/",
    "x-ps-fp": "06999ae0c2fa02880528b0a549374286",
    "X-Requested-With": "XMLHttpRequest",
}

DIESEL_KEYS = ["DL", "dl", "DIESEL", "diesel"]
PREMIUM_DIESEL_KEYS = ["PDL", "pdl", "PREMIUM_DIESEL", "PREM_DIESEL"]


def _raw_stations() -> list[dict]:
    with httpx.Client(timeout=30) as client:
        resp = client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
        resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    if "message" in data:
        msg = data["message"]
        if isinstance(msg, dict) and "list" in msg:
            return msg["list"]
        if isinstance(msg, list):
            return msg
    if "list" in data:
        return data["list"]
    for v in data.values():
        if isinstance(v, list) and v:
            return v
    return []


def fetch_and_normalise() -> tuple[list[dict], list[dict]]:
    """Returns (price_rows, no_price_stations)."""
    stations = _raw_stations()
    price_rows: list[dict] = []
    no_price_stations: list[dict] = []

    for station in stations:
        if not station_matches_target(station):
            continue

        prices = station.get("prices", {})
        name = station.get("name", "Unknown")
        brand = station.get("brand", "")
        town = extract_town(station)
        address = station.get("address", "")

        price = None
        updated_dt = None

        if isinstance(prices, dict):
            for key in DIESEL_KEYS + PREMIUM_DIESEL_KEYS:
                if key not in prices:
                    continue
                val = prices[key]
                if isinstance(val, (int, float)):
                    price = float(val)
                elif isinstance(val, dict):
                    amt = val.get("amount") or val.get("price") or val.get("value")
                    if amt is not None:
                        price = float(amt)
                    ts_raw = val.get("updated") or val.get("lastUpdated") or val.get("date")
                    updated_dt = parse_updated(ts_raw)
                if price is not None:
                    break

        if price is not None:
            price_rows.append({
                "name": name,
                "brand": brand,
                "town": town,
                "fuel_type": "Diesel",
                "price": price,
                "updated_dt": updated_dt,
                "stale": is_stale(updated_dt),
            })
        else:
            no_price_stations.append({
                "name": name, "brand": brand, "town": town, "address": address,
            })

    return price_rows, no_price_stations
