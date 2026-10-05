import re
import unicodedata
from typing import Any

import httpx

from app.schemas.location import LocationKind, LocationSuggestion

PHOTON_SEARCH_URL = "https://photon.komoot.io/api/"
PHOTON_LIMIT = 12

_ALLOWED_TYPES: dict[LocationKind, set[str]] = {
    "departure": {"city", "town"},
    "destination": {"city", "town", "region", "state", "island", "country"},
}
_TYPE_ALIASES = {
    "province": "region",
    "archipelago": "island",
}
_TYPE_PRIORITY = {
    "country": 0,
    "city": 1,
    "town": 2,
    "island": 3,
    "region": 4,
    "state": 5,
}


class LocationProviderError(RuntimeError):
    pass


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]+", "", decomposed)


def _location_type(properties: dict[str, Any]) -> str:
    raw = str(properties.get("osm_value") or properties.get("type") or "").casefold()
    return _TYPE_ALIASES.get(raw, raw)


def _canonical_label(properties: dict[str, Any], location_type: str) -> str:
    name = str(properties["name"]).strip()
    if location_type == "country":
        return name

    candidates: list[str] = [name]
    if location_type in {"city", "town"}:
        candidates.extend(str(properties.get(key) or "").strip() for key in ("state", "region"))
    candidates.append(str(properties.get("country") or "").strip())

    parts: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalized(candidate)
        if candidate and normalized and normalized not in seen:
            parts.append(candidate)
            seen.add(normalized)
    return ", ".join(parts)


def _parse_feature(feature: object, kind: LocationKind) -> LocationSuggestion | None:
    if not isinstance(feature, dict):
        return None
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None

    location_type = _location_type(properties)
    if location_type not in _ALLOWED_TYPES[kind]:
        return None
    name = properties.get("name")
    country_code = properties.get("countrycode")
    coordinates = geometry.get("coordinates")
    if (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(country_code, str)
        or len(country_code.strip()) != 2
        or not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        return None

    try:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        osm_type = str(properties.get("osm_type") or "feature")
        osm_id = str(properties.get("osm_id") or f"{latitude:.6f}:{longitude:.6f}")
        return LocationSuggestion(
            id=f"{osm_type}:{osm_id}",
            label=_canonical_label(properties, location_type),
            name=name,
            country_code=country_code,
            latitude=latitude,
            longitude=longitude,
            location_type=location_type,
        )
    except (TypeError, ValueError):
        return None


def _rank(result: LocationSuggestion, query: str) -> tuple[int, int, str]:
    normalized_query = _normalized(query)
    normalized_name = _normalized(result.name)
    normalized_label = _normalized(result.label)
    if normalized_query in {normalized_name, normalized_label}:
        match_rank = 0
    elif normalized_name.startswith(normalized_query) or normalized_label.startswith(
        normalized_query
    ):
        match_rank = 1
    elif normalized_query in normalized_name or normalized_query in normalized_label:
        match_rank = 2
    else:
        match_rank = 3
    return (match_rank, _TYPE_PRIORITY[result.location_type], result.label.casefold())


def parse_photon_results(
    payload: object, query: str, kind: LocationKind
) -> list[LocationSuggestion]:
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise LocationProviderError("location provider unavailable")

    parsed = [
        result
        for feature in payload["features"]
        if (result := _parse_feature(feature, kind)) is not None
    ]
    unique: dict[tuple[str, str, float, float], LocationSuggestion] = {}
    for result in parsed:
        key = (
            _normalized(result.label),
            result.country_code,
            round(result.latitude, 5),
            round(result.longitude, 5),
        )
        unique.setdefault(key, result)
    return sorted(unique.values(), key=lambda result: _rank(result, query))[:8]


async def search_locations(
    query: str,
    kind: LocationKind,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[LocationSuggestion]:
    owns_client = client is None
    active_client = client or httpx.AsyncClient()
    try:
        response = await active_client.get(
            PHOTON_SEARCH_URL,
            params={"q": query, "limit": PHOTON_LIMIT, "lang": "en"},
            headers={"User-Agent": "TripWise/1.0 location autocomplete"},
            timeout=8.0,
        )
        response.raise_for_status()
        return parse_photon_results(response.json(), query, kind)
    except LocationProviderError:
        raise
    except Exception:
        raise LocationProviderError("location provider unavailable") from None
    finally:
        if owns_client:
            await active_client.aclose()
