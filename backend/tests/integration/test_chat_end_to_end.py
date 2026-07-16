"""Cross-cutting integration coverage for Phase 3 (extended in Phase 6 for
real SSE streaming): drives POST /chat all the way through with only
GeminiClient mocked — the tool dispatch, a real Phase 2 tool, the real
seeded database, real structured logging, and the real SSE response are all
exercised together, proving every layer this phase adds actually composes,
not just each in isolation.
"""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import structlog
from httpx import ASGITransport, AsyncClient

from app.agent.llm_client import FinalAnswer, ModelToolCalls, TextChunk, ToolCallRequest
from app.main import app
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _agen(events):
    for event in events:
        yield event


def _streaming_mock_client(*round_events: list) -> AsyncMock:
    """A mock GeminiClient whose generate_turn_stream() returns the next
    round's fixture event list on each successive call."""
    mock_client = AsyncMock()

    def stream_for_round(**kwargs):
        idx = stream_for_round.calls
        stream_for_round.calls += 1
        return _agen(round_events[idx])

    stream_for_round.calls = 0
    mock_client.generate_turn_stream = stream_for_round
    return mock_client


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        assert frame.startswith("data: ")
        events.append(json.loads(frame[len("data: ") :]))
    return events


async def test_chat_end_to_end_real_tool_real_db_real_logging(seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]
    mock_client = _streaming_mock_client(
        [
            ModelToolCalls(
                calls=[
                    ToolCallRequest(
                        name="get_revenue_summary",
                        args={
                            "restaurant_id": str(restaurant_id),
                            "start_date": SEED_START_DATE.isoformat(),
                            "end_date": SEED_END_DATE.isoformat(),
                        },
                    )
                ]
            )
        ],
        [
            TextChunk(text="Your revenue over that period was solid."),
            FinalAnswer(text="Your revenue over that period was solid."),
        ],
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
    events = _parse_sse_events(response.text)
    done = next(e for e in events if e["type"] == "done")
    assert done["answer"] == "Your revenue over that period was solid."
    tool_call = done["tool_calls"][0]
    assert tool_call["tool_name"] == "get_revenue_summary"
    # Proves a real Phase 2 tool ran against the real seeded database, not a stub.
    assert tool_call["result"] is not None
    assert float(tool_call["result"]["total_revenue"]) > 0

    logged_events = [entry["event"] for entry in captured]
    assert "agent_turn_started" in logged_events
    assert "tool_call_result" in logged_events
    assert "agent_turn_completed" in logged_events


async def test_chat_malformed_model_tool_call_does_not_crash_and_retries(seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]
    mock_client = _streaming_mock_client(
        # First round: the model hands back a garbage restaurant_id.
        [
            ModelToolCalls(
                calls=[
                    ToolCallRequest(
                        name="get_revenue_summary",
                        args={
                            "restaurant_id": "not-a-real-uuid",
                            "start_date": SEED_START_DATE.isoformat(),
                            "end_date": SEED_END_DATE.isoformat(),
                        },
                    )
                ]
            )
        ],
        [
            TextChunk(text="Sorry, something went wrong looking that up."),
            FinalAnswer(text="Sorry, something went wrong looking that up."),
        ],
    )

    async with await _client() as client:
        with patch("app.agent.insights.GeminiClient", return_value=mock_client):
            response = await client.post(
                "/chat",
                json={"restaurant_id": str(restaurant_id), "question": "how did I do?"},
            )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done = next(e for e in events if e["type"] == "done")
    tool_call = done["tool_calls"][0]
    assert tool_call["error"] is not None
    assert mock_client.generate_turn_stream.calls == 2
