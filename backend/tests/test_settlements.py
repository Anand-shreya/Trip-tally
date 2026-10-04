from decimal import Decimal


def test_settlement_greedily_matches_debtors_and_creditors_deterministically():
    from app.schemas.expense import TravelerBalance
    from app.services.settlement_service import calculate_settlements

    balances = [
        TravelerBalance(traveler_id="s", traveler="Shreya", paid=10000, owed=7000, net=3000),
        TravelerBalance(traveler_id="r", traveler="Rahul", paid=8000, owed=7000, net=1000),
        TravelerBalance(traveler_id="a", traveler="Amit", paid=4500, owed=7000, net=-2500),
        TravelerBalance(traveler_id="n", traveler="Ananya", paid=5500, owed=7000, net=-1500),
    ]

    settlements = calculate_settlements(balances)

    assert [(item.from_traveler, item.to_traveler, item.amount) for item in settlements] == [
        ("Amit", "Shreya", Decimal("2500.00")),
        ("Ananya", "Shreya", Decimal("500.00")),
        ("Ananya", "Rahul", Decimal("1000.00")),
    ]
    assert sum(item.amount for item in settlements) == Decimal("4000.00")


def test_balances_conserve_money_for_payers_and_owed_shares(db):
    from test_expenses import equal_payload, expense_trip

    from app.services.expense_service import create_expense
    from app.services.settlement_service import calculate_balances

    trip = expense_trip(db)
    create_expense(db, trip, equal_payload(trip, "100.00"), "balance-1")

    balances = calculate_balances(db, trip)

    assert sum(item.paid for item in balances) == Decimal("100.00")
    assert sum(item.owed for item in balances) == Decimal("100.00")
    assert sum(item.net for item in balances) == Decimal("0.00")
