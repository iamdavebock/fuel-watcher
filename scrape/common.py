"""Shared constants and helpers for fuel-watcher scrapers."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ADELAIDE_TZ = ZoneInfo("Australia/Adelaide")

REGIONS: dict[str, dict] = {
    "riverland": {
        "label": "Riverland",
        "route_start": "Gawler",
        "route_end": "Renmark",
        "bbox": {"neLat": "-34.00", "neLng": "140.80", "swLat": "-34.85", "swLng": "138.70"},
        "target_towns": [
            "gawler", "nuriootpa", "angaston", "tanunda", "truro", "blanchetown",
            "waikerie", "barmera", "berri", "glossop", "monash", "renmark",
            "paringa", "loxton", "roseworthy", "kapunda", "freeling",
            "kingston on murray", "cadell", "moorook", "cobdogla",
        ],
        "route_order": [
            "gawler", "roseworthy", "freeling", "kapunda",
            "nuriootpa", "angaston", "tanunda",
            "truro", "blanchetown",
            "waikerie", "cadell", "kingston on murray",
            "moorook", "cobdogla", "barmera",
            "berri", "glossop", "monash",
            "loxton", "renmark", "paringa",
        ],
    },
    "yorke": {
        "label": "Yorke Peninsula",
        "route_start": "Bolivar",
        "route_end": "Edithburgh",
        "bbox": {"neLat": "-33.50", "neLng": "138.65", "swLat": "-35.20", "swLng": "137.20"},
        "target_towns": [
            "bolivar", "two wells", "dublin", "port wakefield", "balaklava",
            "snowtown", "port broughton", "mundoora", "kadina", "wallaroo",
            "moonta", "ardrossan", "maitland", "port victoria", "minlaton",
            "yorketown", "stansbury", "edithburgh", "warooka", "port vincent",
            "curramulka", "pine point", "wool bay", "clinton",
        ],
        "route_order": [
            "bolivar", "two wells", "dublin", "port wakefield",
            "balaklava", "snowtown", "port broughton",
            "kadina", "wallaroo", "moonta",
            "ardrossan", "maitland", "port victoria",
            "minlaton", "yorketown", "stansbury", "edithburgh",
            "warooka", "port vincent", "curramulka",
        ],
    },
    "fleurieu": {
        "label": "Fleurieu Peninsula",
        "route_start": "Reynella",
        "route_end": "Victor Harbor",
        "bbox": {"neLat": "-34.95", "neLng": "139.10", "swLat": "-35.75", "swLng": "138.25"},
        "target_towns": [
            "reynella", "morphett vale", "noarlunga", "port noarlunga", "old noarlunga",
            "christie downs", "hackham", "mclaren vale", "mclaren flat", "willunga",
            "aldinga", "aldinga beach", "sellicks beach", "yankalilla", "normanville",
            "myponga", "goolwa", "milang", "port elliot", "encounter bay",
            "victor harbor", "middleton", "currency creek", "strathalbyn",
            "hindmarsh island", "seaford", "maslin beach", "moana",
        ],
        "route_order": [
            "reynella", "morphett vale", "seaford", "moana", "noarlunga",
            "port noarlunga", "old noarlunga", "christie downs", "hackham",
            "mclaren vale", "mclaren flat", "willunga",
            "aldinga", "aldinga beach", "maslin beach", "sellicks beach",
            "yankalilla", "normanville", "myponga",
            "strathalbyn", "milang", "currency creek",
            "goolwa", "hindmarsh island",
            "middleton", "port elliot",
            "encounter bay", "victor harbor",
        ],
    },
    "southeast": {
        "label": "Southeast SA",
        "route_start": "Mt Barker",
        "route_end": "Mt Gambier",
        "bbox": {"neLat": "-34.90", "neLng": "141.10", "swLat": "-38.10", "swLng": "138.70"},
        "target_towns": [
            "mt barker", "mount barker", "callington", "murray bridge",
            "tailem bend", "meningie", "tintinara", "keith",
            "bordertown", "naracoorte", "penola",
            "kingston se", "kingston", "robe", "beachport",
            "millicent", "mt gambier", "mount gambier",
            "mannum",
        ],
        "route_order": [
            "mt barker", "mount barker", "callington",
            "murray bridge", "mannum",
            "tailem bend", "meningie",
            "tintinara", "keith",
            "bordertown", "naracoorte", "penola",
            "kingston", "kingston se", "robe",
            "beachport", "millicent",
            "mt gambier", "mount gambier",
        ],
    },
    "eyre": {
        "label": "Eyre Peninsula",
        "route_start": "Port Wakefield",
        "route_end": "Ceduna",
        "bbox": [
            {"neLat": "-31.80", "neLng": "138.30", "swLat": "-34.90", "swLng": "136.00"},
            {"neLat": "-31.80", "neLng": "136.00", "swLat": "-34.90", "swLng": "133.40"},
        ],
        "target_towns": [
            "port wakefield", "port pirie", "port augusta", "whyalla",
            "iron knob", "kimba", "cowell", "cleve", "arno bay",
            "port neil", "port neill", "tumby bay", "port lincoln",
            "coffin bay", "cummins", "lock", "wudinna", "kyancutta",
            "minnipa", "streaky bay", "smoky bay", "ceduna",
        ],
        "route_order": [
            "port wakefield", "port pirie", "port augusta",
            "whyalla", "iron knob", "kimba",
            "cowell", "cleve", "arno bay", "port neil", "port neill",
            "tumby bay", "port lincoln", "coffin bay",
            "cummins", "lock", "wudinna", "kyancutta",
            "minnipa", "streaky bay", "smoky bay", "ceduna",
        ],
    },
}

# Backward-compat aliases (point at Riverland)
TARGET_TOWNS = REGIONS["riverland"]["target_towns"]
ROUTE_ORDER = REGIONS["riverland"]["route_order"]


def route_index(town: str, route_order: list[str] | None = None) -> int:
    order = route_order if route_order is not None else ROUTE_ORDER
    t = town.lower()
    for i, name in enumerate(order):
        if name in t or t in name:
            return i
    return len(order)


def station_matches_region(station: dict, target_towns: list[str]) -> bool:
    haystack = " ".join([
        station.get("name", ""),
        station.get("address", ""),
        station.get("suburb", ""),
    ]).lower()
    return any(town in haystack for town in target_towns)


def station_matches_target(station: dict) -> bool:
    """Backward compat — Riverland only."""
    return station_matches_region(station, TARGET_TOWNS)


# Prefix → canonical name. A suburb that *starts with* the prefix gets collapsed.
# Order matters — longer/more-specific prefixes first.
_TOWN_CANONICAL: list[tuple[str, str]] = [
    ("port augusta", "Port Augusta"),
    ("whyalla",      "Whyalla"),
    ("port pirie",   "Port Pirie"),
    ("port lincoln", "Port Lincoln"),
    ("mount gambier", "Mt Gambier"),
    ("mt gambier",   "Mt Gambier"),
    ("mount barker", "Mt Barker"),
    ("mt barker",    "Mt Barker"),
    ("port neil",    "Port Neill"),   # catches both "Port Neil" and "Port Neill"
    ("murray bridge","Murray Bridge"),
]


def canonicalize_town(town: str) -> str:
    """Collapse suburb variants (e.g. 'Port Augusta West') to a single canonical name."""
    t = town.lower().strip()
    for prefix, canonical in _TOWN_CANONICAL:
        if t == prefix or t.startswith(prefix + " "):
            return canonical
    return town


def extract_town(station: dict) -> str:
    suburb = station.get("suburb", "").strip()
    if suburb:
        return canonicalize_town(suburb.title())
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
    all_towns = [t for r in REGIONS.values() for t in r["target_towns"]]
    for town in all_towns:
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
