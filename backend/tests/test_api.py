from sqlalchemy.orm import Session


def test_complete_trip_lifecycle_api(db: Session):
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

    trip_response = client.post(
        "/api/v1/trips",
        json={
            "name": "Sri Lanka Trip",
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
