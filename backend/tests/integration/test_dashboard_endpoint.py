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


async def test_dashboard_returns_kpis_trend_and_top_items(seeded_restaurants, monkeypatch):
    monkeypatch.setattr("app.api.dashboard.date", _FixedDate)
    restaurant_id = seeded_restaurants["Golden Skillet"]

    async with await _client() as client:
        response = await client.get("/dashboard", params={"restaurant_id": str(restaurant_id)})

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    data = body["data"]

    assert "total_revenue" in data["kpis"]
    assert "transaction_count" in data["kpis"]
    assert "average_ticket" in data["kpis"]
    assert float(data["kpis"]["total_revenue"]) > 0

    assert len(data["revenue_trend"]) == 7
    assert {"day", "revenue"} <= data["revenue_trend"][0].keys()

    assert len(data["top_items"]) <= 5
    quantities = [item["total_quantity"] for item in data["top_items"]]
    assert quantities == sorted(quantities, reverse=True)


async def test_dashboard_nonexistent_restaurant_returns_404():
    async with await _client() as client:
        response = await client.get("/dashboard", params={"restaurant_id": str(uuid.uuid4())})

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "restaurant_not_found"
