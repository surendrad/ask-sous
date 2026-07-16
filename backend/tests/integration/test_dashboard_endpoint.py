import uuid
from datetime import date

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.seed.generators import SEED_END_DATE


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _FixedDate(date):
    """Pins `date.today()` to a date inside the seed window so this test's
    pass/fail doesn't depend on how much real time has passed since
    SEED_END_DATE — the seed data is frozen, but a bare `date.today()`
    isn't. Mirrors test_revenue_summary_integration.py's own
    SEED_END_DATE-anchoring pattern."""

    @classmethod
    def today(cls) -> date:
        return SEED_END_DATE


async def test_dashboard_single_location_returns_one_location_with_kpis_trend_and_top_items(
    seeded_restaurants, monkeypatch
):
    monkeypatch.setattr("app.api.dashboard.date", _FixedDate)
    restaurant_id = seeded_restaurants["Golden Skillet"]

    async with await _client() as client:
        response = await client.get("/dashboard", params={"restaurant_ids": [str(restaurant_id)]})

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    data = body["data"]

    assert len(data["locations"]) == 1
    location = data["locations"][0]
    assert location["restaurant_id"] == str(restaurant_id)
    assert location["restaurant_name"] == "Golden Skillet"
    assert "total_revenue" in location["kpis"]
    assert "transaction_count" in location["kpis"]
    assert "average_ticket" in location["kpis"]
    assert float(location["kpis"]["total_revenue"]) > 0

    assert len(location["revenue_trend"]) == 7
    assert {"day", "revenue"} <= location["revenue_trend"][0].keys()

    assert data["totals"]["total_revenue"] == location["kpis"]["total_revenue"]
    assert data["totals"]["transaction_count"] == location["kpis"]["transaction_count"]

    assert data["top_items"] is not None
    assert len(data["top_items"]) <= 5
    quantities = [item["total_quantity"] for item in data["top_items"]]
    assert quantities == sorted(quantities, reverse=True)

    assert 0 <= float(location["upsell_attach_rate"]) <= 1


async def test_dashboard_multi_location_returns_one_entry_per_restaurant_and_aggregated_totals(
    seeded_restaurants, monkeypatch
):
    monkeypatch.setattr("app.api.dashboard.date", _FixedDate)
    ids = [
        seeded_restaurants["Golden Skillet"],
        seeded_restaurants["Bella Notte"],
        seeded_restaurants["Sakura Table"],
    ]

    async with await _client() as client:
        response = await client.get(
            "/dashboard", params={"restaurant_ids": [str(rid) for rid in ids]}
        )

    assert response.status_code == 200
    body = response.json()
    data = body["data"]

    assert len(data["locations"]) == 3
    assert [loc["restaurant_id"] for loc in data["locations"]] == [str(rid) for rid in ids]
    assert {loc["restaurant_name"] for loc in data["locations"]} == {
        "Golden Skillet",
        "Bella Notte",
        "Sakura Table",
    }
    for location in data["locations"]:
        assert float(location["kpis"]["total_revenue"]) > 0
        assert len(location["revenue_trend"]) == 7
        assert 0 <= float(location["upsell_attach_rate"]) <= 1

    expected_total_revenue = sum(float(loc["kpis"]["total_revenue"]) for loc in data["locations"])
    assert abs(float(data["totals"]["total_revenue"]) - expected_total_revenue) < 0.01
    expected_transaction_count = sum(loc["kpis"]["transaction_count"] for loc in data["locations"])
    assert data["totals"]["transaction_count"] == expected_transaction_count

    assert data["top_items"] is None


async def test_dashboard_nonexistent_restaurant_returns_404():
    async with await _client() as client:
        response = await client.get("/dashboard", params={"restaurant_ids": [str(uuid.uuid4())]})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "restaurant_not_found"


async def test_dashboard_one_nonexistent_among_multiple_returns_404(seeded_restaurants):
    ids = [str(seeded_restaurants["Golden Skillet"]), str(uuid.uuid4())]

    async with await _client() as client:
        response = await client.get("/dashboard", params={"restaurant_ids": ids})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "restaurant_not_found"
