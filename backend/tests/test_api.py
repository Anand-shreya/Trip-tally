from datetime import date

from sqlalchemy.orm import Session


def api_client(db: Session):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.database import get_db
    from app.main import create_app
    from app.models import User

    settings = get_settings()
    if db.get(User, settings.demo_user_id) is None:
        db.add(User(id=settings.demo_user_id, name="Demo", email=settings.demo_user_email))
        db.commit()
    app = create_app(init_database=False)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_complete_trip_lifecycle_api(db: Session, monkeypatch):
    from test_planning import FakePlanningProvider, successful_weather

    from app.services import planning_service

    monkeypatch.setattr(planning_service, "get_weather_report", successful_weather)
    monkeypatch.setattr(
        planning_service,
        "build_gemini_planning_provider",
        lambda: FakePlanningProvider(),
    )
    client = api_client(db)

    trip_response = client.post(
        "/api/v1/trips",
        json={
            "name": "Sri Lanka Trip",
            "departure_city": "Delhi",
            "destination": "Sri Lanka",
            "start_date": "2026-09-05",
            "number_of_days": 3,
            "budget": "30000",
            "currency": "INR",
            "travel_style": "COMFORTABLE",
        },
    )
    assert trip_response.status_code == 201
    trip_id = trip_response.json()["trip_id"]

    traveler_ids = []
    for name in ["Shreya", "Rahul", "Amit"]:
        response = client.post(f"/api/v1/trips/{trip_id}/travelers", json={"name": name})
        assert response.status_code == 201
        traveler_ids.append(response.json()["id"])

    analysis = client.post(f"/api/v1/trips/{trip_id}/analyze")
    assert analysis.status_code == 200
    assert analysis.json()["status"] == "READY"
    place_ids = [place["id"] for place in analysis.json()["places"][:2]]

    selected = client.post(f"/api/v1/trips/{trip_id}/places/select", json={"place_ids": place_ids})
    assert selected.status_code == 200
    assert len(selected.json()) == 2

    generated = client.post(f"/api/v1/trips/{trip_id}/itinerary/generate")
    assert generated.status_code == 202
    assert generated.json()["status"] == "SUCCESS"
    itinerary = client.get(f"/api/v1/trips/{trip_id}/itinerary")
    assert len(itinerary.json()) == 3

    expense = client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers={"Idempotency-Key": "dinner-1"},
        json={
            "description": "Dinner",
            "amount": "1200",
            "currency": "INR",
            "category": "FOOD",
            "paid_by": traveler_ids[1],
            "expense_date": "2026-09-05",
            "included_travelers": traveler_ids,
            "split_type": "EQUAL",
        },
    )
    assert expense.status_code == 201
    assert sum(float(split["share_amount"]) for split in expense.json()["splits"]) == 1200

    assert len(client.get(f"/api/v1/trips/{trip_id}/expenses?category=FOOD").json()) == 1
    balances = client.get(f"/api/v1/trips/{trip_id}/balances").json()["balances"]
    assert sum(float(item["net"]) for item in balances) == 0
    assert client.get(f"/api/v1/trips/{trip_id}/settlements").status_code == 200

    summary = client.get(f"/api/v1/trips/{trip_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["total_spent"] == "1200.00"
    assert summary.json()["remaining"] == "28800.00"


def test_missing_trip_uses_consistent_detail_error(db: Session):
    from fastapi.testclient import TestClient

    from app.db.database import get_db
    from app.main import create_app

    app = create_app(init_database=False)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).get("/api/v1/trips/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


def test_trip_can_be_archived_and_restored_without_losing_its_status(db: Session):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.database import get_db
    from app.main import create_app
    from app.models import User

    settings = get_settings()
    db.add(User(id=settings.demo_user_id, name="Demo", email=settings.demo_user_email))
    db.commit()

    app = create_app(init_database=False)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    created = client.post(
        "/api/v1/trips",
        json={
            "name": "Quiet coast",
            "departure_city": "Bengaluru",
            "destination": "Gokarna",
            "start_date": "2026-11-10",
            "number_of_days": 4,
            "budget": "24000",
            "currency": "INR",
            "travel_style": "BUDGET",
        },
    )
    trip_id = created.json()["trip_id"]

    archived = client.post(f"/api/v1/trips/{trip_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "PLANNING"
    assert archived.json()["is_archived"] is True
    assert archived.json()["archived_at"] is not None

    listed_trip = next(trip for trip in client.get("/api/v1/trips").json() if trip["id"] == trip_id)
    assert listed_trip["is_archived"] is True

    restored = client.delete(f"/api/v1/trips/{trip_id}/archive")
    assert restored.status_code == 200
    assert restored.json()["status"] == "PLANNING"
    assert restored.json()["is_archived"] is False
    assert restored.json()["archived_at"] is None


def test_analysis_api_requires_departure_city_for_legacy_trip(db: Session):
    from app.core.config import get_settings
    from app.models import Trip, User

    settings = get_settings()
    user = User(id=settings.demo_user_id, name="Demo", email=settings.demo_user_email)
    trip = Trip(
        user=user,
        name="Legacy",
        destination="Goa",
        start_date=date(2027, 1, 10),
        end_date=date(2027, 1, 12),
        number_of_days=3,
        base_currency="INR",
        travel_style="BUDGET",
        status="PLANNING",
    )
    db.add(trip)
    db.commit()

    response = api_client(db).post(f"/api/v1/trips/{trip.id}/analyze", json={})

    assert response.status_code == 422
    assert response.json() == {"detail": "Departure city is required before analysis"}


def test_analysis_api_returns_only_safe_provider_error(db: Session, monkeypatch):
    from test_planning import FakePlanningProvider, successful_weather

    from app.providers.gemini_planning import PlanningProviderUnavailable
    from app.services import planning_service

    client = api_client(db)
    created = client.post(
        "/api/v1/trips",
        json={
            "name": "Provider failure",
            "departure_city": "Delhi",
            "destination": "Kyoto",
            "start_date": "2027-04-04",
            "number_of_days": 5,
            "currency": "INR",
            "travel_style": "COMFORTABLE",
        },
    )
    trip_id = created.json()["trip_id"]
    monkeypatch.setattr(planning_service, "get_weather_report", successful_weather)
    monkeypatch.setattr(
        planning_service,
        "build_gemini_planning_provider",
        lambda: FakePlanningProvider(
            budget_error=PlanningProviderUnavailable("key=secret-key upstream body")
        ),
    )

    response = client.post(f"/api/v1/trips/{trip_id}/analyze", json={})

    assert response.status_code == 502
    assert response.json() == {"detail": {"code": "budget_unavailable"}}
    assert "secret-key" not in response.text
    assert "upstream" not in response.text


def test_analysis_read_never_calls_providers(db: Session, monkeypatch):
    from test_planning import FakePlanningProvider, successful_weather

    from app.services import planning_service

    client = api_client(db)
    created = client.post(
        "/api/v1/trips",
        json={
            "name": "Persisted analysis",
            "departure_city": "Delhi",
            "destination": "Kyoto",
            "start_date": "2027-04-04",
            "number_of_days": 5,
            "currency": "INR",
            "travel_style": "COMFORTABLE",
        },
    )
    trip_id = created.json()["trip_id"]
    monkeypatch.setattr(planning_service, "get_weather_report", successful_weather)
    monkeypatch.setattr(
        planning_service,
        "build_gemini_planning_provider",
        lambda: FakePlanningProvider(),
    )
    analyzed = client.post(f"/api/v1/trips/{trip_id}/analyze", json={})
    assert analyzed.status_code == 200

    def unexpected_provider_call():
        raise AssertionError("analysis read contacted a provider")

    monkeypatch.setattr(
        planning_service,
        "build_gemini_planning_provider",
        unexpected_provider_call,
    )
    response = client.get(f"/api/v1/trips/{trip_id}/analysis")

    assert response.status_code == 200
    assert response.json() == analyzed.json()


def test_analysis_read_returns_404_before_first_success(db: Session):
    client = api_client(db)
    created = client.post(
        "/api/v1/trips",
        json={
            "name": "Not analyzed",
            "departure_city": "Delhi",
            "destination": "Kyoto",
            "start_date": "2027-04-04",
            "number_of_days": 5,
            "currency": "INR",
            "travel_style": "COMFORTABLE",
        },
    )

    response = client.get(f"/api/v1/trips/{created.json()['trip_id']}/analysis")

    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis not found"}
