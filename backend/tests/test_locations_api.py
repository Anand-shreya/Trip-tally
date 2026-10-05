from sqlalchemy.orm import Session
from test_api import api_client


def test_location_search_api_returns_canonical_structured_options(db: Session, monkeypatch):
    from app.api import locations as locations_api
    from app.schemas.location import LocationSuggestion

    observed: dict[str, str] = {}

    async def fake_search(query: str, kind: str):
        observed.update(query=query, kind=kind)
        return [
            LocationSuggestion(
                id="R:536807",
                label="Sri Lanka",
                name="Sri Lanka",
                country_code="LK",
                latitude=7.8774,
                longitude=80.7011,
                location_type="country",
            )
        ]

    monkeypatch.setattr(locations_api, "search_locations", fake_search)

    response = api_client(db).get(
        "/api/v1/locations/search",
        params={"q": "Sri Lanka", "kind": "destination"},
    )

    assert response.status_code == 200
    assert observed == {"query": "Sri Lanka", "kind": "destination"}
    assert response.json() == [
        {
            "id": "R:536807",
            "label": "Sri Lanka",
            "name": "Sri Lanka",
            "country_code": "LK",
            "latitude": 7.8774,
            "longitude": 80.7011,
            "location_type": "country",
        }
    ]


def test_location_search_api_requires_two_characters(db: Session):
    response = api_client(db).get(
        "/api/v1/locations/search", params={"q": "S", "kind": "destination"}
    )

    assert response.status_code == 422


def test_trip_api_round_trips_selected_location_coordinates(db: Session):
    client = api_client(db)
    created = client.post(
        "/api/v1/trips",
        json={
            "name": "Island loop",
            "departure_city": "Delhi, India",
            "destination": "Sri Lanka",
            "departure_location": {
                "label": "Delhi, India",
                "country_code": "IN",
                "latitude": 28.6274,
                "longitude": 77.1717,
                "location_type": "city",
            },
            "destination_location": {
                "label": "Sri Lanka",
                "country_code": "LK",
                "latitude": 7.8774,
                "longitude": 80.7011,
                "location_type": "country",
            },
            "start_date": "2027-02-10",
            "number_of_days": 7,
        },
    )

    assert created.status_code == 201
    trip = client.get(f"/api/v1/trips/{created.json()['trip_id']}")

    assert trip.status_code == 200
    assert trip.json()["departure_location"] == {
        "label": "Delhi, India",
        "country_code": "IN",
        "latitude": 28.6274,
        "longitude": 77.1717,
        "location_type": "city",
    }
    assert trip.json()["destination_location"] == {
        "label": "Sri Lanka",
        "country_code": "LK",
        "latitude": 7.8774,
        "longitude": 80.7011,
        "location_type": "country",
    }
