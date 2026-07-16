"""Cross-cutting integration coverage for Phase 3: drives POST /chat all the
way through with only GeminiClient mocked — the tool dispatch, a real Phase 2
tool, the real seeded database, real structured logging, and the real
response envelope are all exercised together, proving every layer this
phase adds actually composes, not just each in isolation.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import structlog
from httpx import ASGITransport, AsyncClient

from app.agent.llm_client import FinalAnswer, ToolCallRequest
from app.main import app
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_chat_end_to_end_real_tool_real_db_real_logging(seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={
                        "restaurant_id": str(restaurant_id),
                        "start_date": SEED_START_DATE.isoformat(),
                        "end_date": SEED_END_DATE.isoformat(),
                    },
                )
            ],
            FinalAnswer(text="Your revenue over that period was solid."),
        ]
    )

    async with await _client() as client:
        with (
            patch("app.agent.insights.GeminiClient", return_value=mock_client),
            structlog.testing.capture_logs(
                processors=(structlog.contextvars.merge_contextvars,)
            ) as captured,
        ):
            response = await client.post(
                "/chat",
                json={
                    "restaurant_id": str(restaurant_id),
                    "question": "how did I do last month?",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["answer"] == "Your revenue over that period was solid."
    tool_call = body["data"]["tool_calls"][0]
    assert tool_call["tool_name"] == "get_revenue_summary"
    # Proves a real Phase 2 tool ran against the real seeded database, not a stub.
    assert tool_call["result"] is not None
    assert float(tool_call["result"]["total_revenue"]) > 0

    events = [entry["event"] for entry in captured]
    assert "agent_turn_started" in events
    assert "tool_call_result" in events
    assert "agent_turn_completed" in events


async def test_chat_malformed_model_tool_call_does_not_crash_and_retries(seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            # First round: the model hands back a garbage restaurant_id.
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={
                        "restaurant_id": "not-a-real-uuid",
                        "start_date": SEED_START_DATE.isoformat(),
                        "end_date": SEED_END_DATE.isoformat(),
                    },
                )
            ],
            FinalAnswer(text="Sorry, something went wrong looking that up."),
        ]
    )

    async with await _client() as client:
        with patch("app.agent.insights.GeminiClient", return_value=mock_client):
            response = await client.post(
                "/chat",
                json={"restaurant_id": str(restaurant_id), "question": "how did I do?"},
            )

    assert response.status_code == 200
    body = response.json()
    tool_call = body["data"]["tool_calls"][0]
    assert tool_call["error"] is not None
    assert mock_client.generate_turn.await_count == 2
