"""Cross-cutting Phase 4 coverage: drives POST /chat all the way through
with only GeminiClient/EmbeddingClient mocked — the tool dispatch, real
pgvector query against hand-crafted embedded reviews, real logging, and the
real response envelope are all exercised together for the new
search_customer_reviews tool.
"""

import json
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent.llm_client import FinalAnswer, ModelToolCalls, TextChunk, ToolCallRequest
from app.agent.tools import vector_search
from app.main import app

_DIM = 768


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _agen(events):
    for event in events:
        yield event


def _streaming_mock_client(*round_events: list) -> AsyncMock:
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


async def test_chat_end_to_end_with_review_search_tool(admin_engine, seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]

    async with admin_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id, review_text FROM reviews WHERE restaurant_id = :rid LIMIT 1"),
            {"rid": restaurant_id},
        )
        review_id, review_text = result.one()
        vector = [1.0] * _DIM
        await conn.execute(
            text("UPDATE reviews SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": vector_search._format_vector_literal(vector), "id": review_id},
        )

    mock_gemini = _streaming_mock_client(
        [
            ModelToolCalls(
                calls=[
                    ToolCallRequest(
                        name="search_customer_reviews",
                        args={"restaurant_id": str(restaurant_id), "query": "service"},
                    )
                ]
            )
        ],
        [
            TextChunk(text="Customers mentioned the service in their reviews."),
            FinalAnswer(text="Customers mentioned the service in their reviews."),
        ],
    )
    mock_embedding = AsyncMock()
    mock_embedding.embed_texts = AsyncMock(return_value=[vector])

    async with await _client() as client:
        with (
            patch("app.agent.insights.GeminiClient", return_value=mock_gemini),
            patch("app.agent.tools.vector_search.EmbeddingClient", return_value=mock_embedding),
        ):
            response = await client.post(
                "/chat",
                json={
                    "restaurant_id": str(restaurant_id),
                    "question": "what are customers saying about the service?",
                },
            )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done = next(e for e in events if e["type"] == "done")
    tool_call = done["tool_calls"][0]
    assert tool_call["tool_name"] == "search_customer_reviews"
    assert tool_call["result"]["matches"][0]["review_text"] == review_text
