"""Cross-cutting Phase 5 coverage: drives POST /campaigns all the way
through with only GeminiClient/EmbeddingClient mocked — the brand voice
lookup, real pgvector query against a hand-crafted embedded campaign, real
logging, and the real response envelope are all exercised together.
"""

from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent.llm_client import FinalAnswer
from app.agent.tools import vector_search
from app.main import app

_DIM = 768


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_campaigns_end_to_end_with_past_campaign_retrieval(admin_engine, seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]

    async with admin_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id, copy_text FROM campaigns WHERE restaurant_id = :rid LIMIT 1"),
            {"rid": restaurant_id},
        )
        campaign_id, copy_text = result.one()
        vector = [1.0] * _DIM
        await conn.execute(
            text("UPDATE campaigns SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": vector_search._format_vector_literal(vector), "id": campaign_id},
        )

    mock_gemini = AsyncMock()
    mock_gemini.generate_turn = AsyncMock(
        return_value=FinalAnswer(text="Come try our new weekend brunch special!")
    )
    mock_embedding = AsyncMock()
    mock_embedding.embed_texts = AsyncMock(return_value=[vector])

    async with await _client() as client:
        with (
            patch("app.agent.campaigns.GeminiClient", return_value=mock_gemini),
            patch("app.agent.tools.vector_search.EmbeddingClient", return_value=mock_embedding),
        ):
            response = await client.post(
                "/campaigns",
                json={"restaurant_id": str(restaurant_id), "brief": "Announce weekend brunch"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["copy_text"] == "Come try our new weekend brunch special!"
    assert body["data"]["examples_used"][0]["copy_text"] == copy_text
    assert body["data"]["model"] == "gemini-2.5-pro"
