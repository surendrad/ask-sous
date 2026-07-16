from httpx import ASGITransport, AsyncClient

from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_get_restaurants_returns_all_five_seeded_restaurants(seeded_restaurants):
    async with await _client() as client:
        response = await client.get("/restaurants")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    names = [r["name"] for r in body["data"]["restaurants"]]
    assert set(names) == set(seeded_restaurants.keys())
    assert names == sorted(names)


async def test_get_restaurants_returns_id_and_name_only(seeded_restaurants):
    async with await _client() as client:
        response = await client.get("/restaurants")

    restaurant = response.json()["data"]["restaurants"][0]
    assert set(restaurant.keys()) == {"id", "name"}
