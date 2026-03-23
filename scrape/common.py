"""Shared constants and helpers for fuel-watcher scrapers."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ADELAIDE_TZ = ZoneInfo("Australia/Adelaide")

TARGET_TOWNS = [
    "gawler", "nuriootpa", "angaston", "tanunda", "truro", "blanchetown",
    "waikerie", "barmera", "berri", "glossop", "monash", "renmark",
    "paringa", "loxton", "roseworthy", "kapunda", "freeling",
    "kingston on murray", "cadell", "moorook", "cobdogla",
]

ROUTE_ORDER = [
    "gawler", "roseworthy", "freeling", "kapunda",
    "nuriootpa", "angaston", "tanunda",
    "truro",
    "blanchetown",
    "waikerie", "cadell", "kingston on murray",
    "moorook", "cobdogla", "barmera",
    "berri", "glossop", "monash",
    "loxton",
    "renmark", "paringa",
]


def route_index(town: str) -> int:
    t = town.lower()
    for i, name in enumerate(ROUTE_ORDER):
        if name in t or t in name:
            return i
    return len(ROUTE_ORDER)


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


def now_adelaide() -> datetime:
    return datetime.now(tz=ADELAIDE_TZ)


def format_timestamp(dt: datetime) -> str:
    return dt.strftime("%A %-d %b %Y, %-I:%M%p %Z").replace("AM", "am").replace("PM", "pm")
