import httpx
import pytest


def photon_feature(
    *,
    name: str,
    location_type: str,
    longitude: float,
    latitude: float,
    country: str = "Sri Lanka",
    country_code: str = "lk",
    state: str | None = None,
) -> dict:
    properties = {
        "osm_id": 100,
        "osm_type": "R",
        "osm_key": "place",
        "osm_value": location_type,
        "name": name,
        "country": country,
        "countrycode": country_code,
    }
    if state:
        properties["state"] = state
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


@pytest.mark.asyncio
async def test_destination_search_filters_pois_and_ranks_normalized_country_exact_match_first():
    from app.providers.locations import search_locations

    payload = {
        "type": "FeatureCollection",
        "features": [
            photon_feature(
                name="Srilanka Restaurant",
                location_type="restaurant",
                longitude=80.01,
                latitude=7.01,
            ),
            photon_feature(
                name="Colombo",
                location_type="city",
                longitude=79.8612,
                latitude=6.9271,
                state="Western Province",
            ),
            photon_feature(
                name="Sri Lanka",
                location_type="country",
                longitude=80.7011,
                latitude=7.8774,
            ),
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "photon.komoot.io"
        assert request.url.path == "/api/"
        assert request.url.params["q"] == "srilanka"
        assert request.url.params["lang"] == "en"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await search_locations("srilanka", "destination", client=client)

    assert [result.label for result in results] == [
        "Sri Lanka",
        "Colombo, Western Province, Sri Lanka",
    ]
    assert results[0].country_code == "LK"
    assert results[0].location_type == "country"
    assert results[0].latitude == 7.8774
    assert results[0].longitude == 80.7011


@pytest.mark.asyncio
async def test_departure_search_returns_only_cities_and_towns():
    from app.providers.locations import search_locations

    payload = {
        "type": "FeatureCollection",
        "features": [
            photon_feature(
                name="Colombo",
                location_type="city",
                longitude=79.8612,
                latitude=6.9271,
                state="Western Province",
            ),
            photon_feature(
                name="Western Province",
                location_type="state",
                longitude=80.0,
                latitude=6.8,
                state="Western Province",
            ),
            photon_feature(
                name="Galle",
                location_type="town",
                longitude=80.217,
                latitude=6.032,
                state="Southern Province",
            ),
        ],
    }

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        results = await search_locations("Col", "departure", client=client)

    assert [result.location_type for result in results] == ["city", "town"]


@pytest.mark.asyncio
async def test_location_provider_failures_expose_one_safe_error():
    from app.providers.locations import LocationProviderError, search_locations

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(503, json={"detail": "private upstream response"})
        )
    ) as client:
        with pytest.raises(LocationProviderError, match="location provider unavailable"):
            await search_locations("Delhi", "departure", client=client)
