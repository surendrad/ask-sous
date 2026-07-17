import uuid
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.agent.campaigns import CampaignGenerationResult
from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.agent.insights import ToolCallRecord
from app.agent.tools.vector_search import SimilarCampaign
from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_campaigns_happy_path_returns_envelope(seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    fixed_result = CampaignGenerationResult(
        copy_text="Tuesdays are slow — 20% off dine-in orders over $20!",
        brand_voice_guide="Warm and playful.",
        examples_used=[
            SimilarCampaign(campaign_id=uuid.uuid4(), copy_text="Old copy.", distance=0.1)
        ],
        model="gemini-2.5-pro",
        tool_calls=[
            ToolCallRecord(
                tool_name="get_weekday_performance",
                arguments={"restaurant_id": str(restaurant_id)},
                result=[{"day_of_week": "Tuesday", "total_revenue": "100.00"}],
                error=None,
            )
        ],
    )

    async with await _client() as client:
        with patch("app.api.campaigns.generate_campaign", AsyncMock(return_value=fixed_result)):
            response = await client.post(
                "/campaigns",
                json={
                    "restaurant_id": str(restaurant_id),
                    "brief": "Create a campaign for our slowest weekday",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["copy_text"] == "Tuesdays are slow — 20% off dine-in orders over $20!"
    assert body["data"]["model"] == "gemini-2.5-pro"
    assert body["data"]["examples_used"][0]["copy_text"] == "Old copy."
    assert body["data"]["tool_calls"][0]["tool_name"] == "get_weekday_performance"


async def test_campaigns_nonexistent_restaurant_returns_404():
    async with await _client() as client:
        response = await client.post(
            "/campaigns", json={"restaurant_id": str(uuid.uuid4()), "brief": "hi"}
        )

    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "restaurant_not_found"


async def test_campaigns_malformed_restaurant_id_returns_422():
    async with await _client() as client:
        response = await client.post(
            "/campaigns", json={"restaurant_id": "not-a-uuid", "brief": "hi"}
        )

    assert response.status_code == 422


async def test_campaigns_agent_unavailable_returns_503_without_leaking_internals(
    seeded_restaurants,
):
    restaurant_id = next(iter(seeded_restaurants.values()))
    async with await _client() as client:
        with patch(
            "app.api.campaigns.generate_campaign",
            AsyncMock(side_effect=AgentUnavailableError("internal secret detail")),
        ):
            response = await client.post(
                "/campaigns", json={"restaurant_id": str(restaurant_id), "brief": "hi"}
            )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "agent_unavailable"
    assert "internal secret detail" not in response.text


async def test_campaigns_agent_incomplete_returns_502(seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    async with await _client() as client:
        with patch(
            "app.api.campaigns.generate_campaign",
            AsyncMock(side_effect=AgentIncompleteError("gave up")),
        ):
            response = await client.post(
                "/campaigns", json={"restaurant_id": str(restaurant_id), "brief": "hi"}
            )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "agent_incomplete"
