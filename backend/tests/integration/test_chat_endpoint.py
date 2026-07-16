import uuid
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.agent.insights import AgentTurnResult, ToolCallRecord
from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_chat_happy_path_returns_envelope(seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    fixed_result = AgentTurnResult(
        answer="Revenue was $500.",
        tool_calls=[
            ToolCallRecord(
                tool_name="get_revenue_summary",
                arguments={"restaurant_id": str(restaurant_id)},
                result={"total_revenue": "500.00"},
                error=None,
            )
        ],
        model="gemini-2.5-flash",
    )

    async with await _client() as client:
        with patch("app.api.chat.answer_question", AsyncMock(return_value=fixed_result)):
            response = await client.post(
                "/chat",
                json={"restaurant_id": str(restaurant_id), "question": "how much did I make?"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["answer"] == "Revenue was $500."
    assert body["data"]["model"] == "gemini-2.5-flash"
    assert body["data"]["tool_calls"][0]["tool_name"] == "get_revenue_summary"


async def test_chat_nonexistent_restaurant_returns_404():
    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(uuid.uuid4()), "question": "hi"}
        )

    assert response.status_code == 404
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "restaurant_not_found"


async def test_chat_malformed_restaurant_id_returns_422():
    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": "not-a-uuid", "question": "hi"}
        )

    assert response.status_code == 422


async def test_chat_agent_unavailable_returns_503_without_leaking_internals(seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    async with await _client() as client:
        with patch(
            "app.api.chat.answer_question",
            AsyncMock(side_effect=AgentUnavailableError("internal secret detail")),
        ):
            response = await client.post(
                "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
            )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "agent_unavailable"
    assert "internal secret detail" not in response.text


async def test_chat_agent_incomplete_returns_502(seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    async with await _client() as client:
        with patch(
            "app.api.chat.answer_question",
            AsyncMock(side_effect=AgentIncompleteError("gave up")),
        ):
            response = await client.post(
                "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
            )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "agent_incomplete"
