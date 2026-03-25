"""PetrolSpy bounding box API source — multi-region."""
from __future__ import annotations

import time
import httpx

from scrape.common import (
    REGIONS, extract_town, is_stale, parse_updated, station_matches_region,
)

SOURCE_NAME = "petrolspy"
DISPLAY_NAME = "PetrolSpy"

API_URL = "https://petrolspy.com.au/webservice-1/station/box"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://petrolspy.com.au/",
    "x-ps-fp": "06999ae0c2fa02880528b0a549374286",
    "X-Requested-With": "XMLHttpRequest",
}

DIESEL_KEYS = ["DL", "dl", "DIESEL", "diesel"]
PREMIUM_DIESEL_KEYS = ["PDL", "pdl", "PREMIUM_DIESEL", "PREM_DIESEL"]


def _raw_stations(bbox: dict) -> list[dict]:
    params = {
        "neLat": bbox["neLat"],
        "neLng": bbox["neLng"],
        "swLat": bbox["swLat"],
        "swLng": bbox["swLng"],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(API_URL, params=params, headers=API_HEADERS)
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


def _extract_price(prices: dict, keys: list[str]) -> tuple[float | None, object]:
    """Return (price, updated_raw) for the first matching key."""
    for key in keys:
        if key not in prices:
            continue
        val = prices[key]
        if isinstance(val, (int, float)):
            return float(val), None
        if isinstance(val, dict):
            amt = val.get("amount") or val.get("price") or val.get("value")
            ts = val.get("updated") or val.get("lastUpdated") or val.get("date")
            if amt is not None:
                return float(amt), ts
    return None, None


def _normalise(stations: list[dict], target_towns: list[str]) -> tuple[list[dict], list[dict]]:
    price_rows: list[dict] = []
    no_price_stations: list[dict] = []

    for station in stations:
        if not station_matches_region(station, target_towns):
            continue

        prices = station.get("prices", {}) or {}
        name = station.get("name", "Unknown")
        brand = station.get("brand", "")
        town = extract_town(station)
        address = station.get("address", "")

        diesel_price, diesel_ts = _extract_price(prices, DIESEL_KEYS)
        premium_price, premium_ts = _extract_price(prices, PREMIUM_DIESEL_KEYS)

        if diesel_price is not None:
            updated_dt = parse_updated(diesel_ts)
            price_rows.append({
                "name": name, "brand": brand, "town": town,
                "fuel_type": "Diesel", "price": diesel_price,
                "updated_dt": updated_dt, "stale": is_stale(updated_dt),
            })

        if premium_price is not None:
            updated_dt = parse_updated(premium_ts)
            price_rows.append({
                "name": name, "brand": brand, "town": town,
                "fuel_type": "Premium Diesel", "price": premium_price,
                "updated_dt": updated_dt, "stale": is_stale(updated_dt),
            })

        if diesel_price is None and premium_price is None:
            no_price_stations.append({
                "name": name, "brand": brand, "town": town, "address": address,
            })

    return price_rows, no_price_stations


def fetch_all_regions() -> dict:
    """
    Fetch all regions in one run. Returns:
    {
        region_key: {
            "label": str,
            "route_start": str,
            "route_end": str,
            "route_order": list[str],
            "price_rows": list[dict],
            "no_price_stations": list[dict],
        }
    }
    """
    results = {}
    region_keys = list(REGIONS.keys())
    for i, region_key in enumerate(region_keys):
        region_cfg = REGIONS[region_key]
        if i > 0:
            time.sleep(1)
        # Support single bbox dict or list of bbox dicts (for large regions)
        bboxes = region_cfg["bbox"] if isinstance(region_cfg["bbox"], list) else [region_cfg["bbox"]]
        stations: list[dict] = []
        for j, bbox in enumerate(bboxes):
            if j > 0:
                time.sleep(1)
            stations.extend(_raw_stations(bbox))
        # Deduplicate by station name+address in case bboxes overlap
        seen: set[str] = set()
        unique: list[dict] = []
        for s in stations:
            key = f"{s.get('name','')}|{s.get('address','')}"
            if key not in seen:
                seen.add(key)
                unique.append(s)
        price_rows, no_price_stations = _normalise(unique, region_cfg["target_towns"])
        results[region_key] = {
            "label": region_cfg["label"],
            "route_start": region_cfg["route_start"],
            "route_end": region_cfg["route_end"],
            "route_order": region_cfg["route_order"],
            "price_rows": price_rows,
            "no_price_stations": no_price_stations,
        }
    return results


def fetch_and_normalise() -> tuple[list[dict], list[dict]]:
    """Legacy single-region interface (Riverland). Kept for backward compat."""
    all_data = fetch_all_regions()
    r = all_data["riverland"]
    return r["price_rows"], r["no_price_stations"]
