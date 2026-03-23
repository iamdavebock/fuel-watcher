"""FuelPrice Australia API client."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.fuelprice.io/v1"
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache"
STATIONS_CACHE = CACHE_DIR / "stations.json"
CITIES_CACHE = CACHE_DIR / "cities.json"
CACHE_TTL = 3600 * 6  # 6 hours


class AuthError(Exception):
    pass


class RateLimitError(Exception):
    pass


class APIError(Exception):
    pass


def get_token() -> str:
    token = os.environ.get("FUELPRICE_API_TOKEN", "").strip()
    if not token or token == "your_token_here":
        raise AuthError("no_token")
    return token


def _client() -> httpx.Client:
    token = get_token()
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=15.0,
    )


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    with _client() as client:
        resp = client.get(path, params=params)

    if resp.status_code == 401:
        raise AuthError("invalid_token")
    if resp.status_code == 429:
        raise RateLimitError("Rate limit exceeded (30 req/min). Wait a moment and try again.")
    if not resp.is_success:
        raise APIError(f"API returned {resp.status_code}: {resp.text[:200]}")

    return resp.json()


# --------------------------------------------------------------------------- #
# Cache helpers
# --------------------------------------------------------------------------- #

def _load_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("_ts", 0) < CACHE_TTL:
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _save_cache(path: Path, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    data["_ts"] = time.time()
    path.write_text(json.dumps(data, indent=2))


# --------------------------------------------------------------------------- #
# API calls
# --------------------------------------------------------------------------- #

def get_fuel_types() -> list[dict]:
    return _get("/fuel-types")


def get_cities() -> list[dict]:
    cached = _load_cache(CITIES_CACHE)
    if cached:
        return cached["cities"]
    data = _get("/cities")
    cities = data if isinstance(data, list) else data.get("data", data)
    _save_cache(CITIES_CACHE, {"cities": cities})
    return cities


def find_city_id(name: str) -> str | None:
    cities = get_cities()
    name_lower = name.lower()
    for city in cities:
        city_name = (city.get("name") or city.get("city") or "").lower()
        if name_lower in city_name or city_name in name_lower:
            return city.get("id") or city.get("city_id")
    return None


def get_stations(location: str) -> list[dict]:
    """Return stations for a location name, using cache where possible."""
    cache_key = location.lower().replace(" ", "_")
    cache_path = CACHE_DIR / f"stations_{cache_key}.json"

    cached = _load_cache(cache_path)
    if cached:
        return cached["stations"]

    # Try city-based lookup first
    params: dict[str, Any] = {}
    city_id = find_city_id(location)
    if city_id:
        params["city_id"] = city_id
    else:
        # Fall back to name/suburb search if API supports it
        params["suburb"] = location

    data = _get("/stations", params=params)
    stations = data if isinstance(data, list) else data.get("data", data)

    if not stations:
        # Last resort: search all stations for name match
        all_data = _get("/stations")
        all_stations = all_data if isinstance(all_data, list) else all_data.get("data", all_data)
        loc_lower = location.lower()
        stations = [
            s for s in all_stations
            if loc_lower in (s.get("suburb") or s.get("city") or s.get("location") or "").lower()
        ]

    _save_cache(cache_path, {"stations": stations})
    return stations


def get_station(station_id: str) -> dict:
    return _get(f"/station/{station_id}")


def get_station_history(station_id: str, hours: int = 48) -> list[dict]:
    data = _get(f"/stations/{station_id}/history", params={"hours": hours})
    return data if isinstance(data, list) else data.get("data", data)


def bust_location_cache(location: str) -> None:
    """Delete the cached station list for a location so next call re-fetches."""
    cache_key = location.lower().replace(" ", "_")
    cache_path = CACHE_DIR / f"stations_{cache_key}.json"
    if cache_path.exists():
        cache_path.unlink()
