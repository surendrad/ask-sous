"""Vector similarity search — qualitative grounding for both Q&A
(`search_reviews`, registered as the sixth LLM-callable tool this phase)
and campaign few-shot retrieval (`search_similar_campaigns`, built now but
wired into Phase 5's campaign generation directly, not the model's
toolset). Cosine distance (`<=>`), a vector literal bound as an ordinary
text parameter and CAST to `vector` in SQL (no asyncpg-level codec
registration needed), no ANN index at this data scale. See
docs/decisions/009-vector-retrieval-tool-design.md.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.agent.embedding_client import EmbeddingClient
from app.agent.tools.db import readonly_connection

DEFAULT_TOP_K = 5
MAX_TOP_K = 20

_REVIEW_SEARCH_SQL = text(
    "SELECT id, review_text, rating, embedding <=> CAST(:vector_literal AS vector) AS distance "
    "FROM reviews "
    "WHERE restaurant_id = :restaurant_id AND embedding IS NOT NULL "
    "ORDER BY distance "
    "LIMIT :top_k"
)

_CAMPAIGN_SEARCH_SQL = text(
    "SELECT id, copy_text, embedding <=> CAST(:vector_literal AS vector) AS distance "
    "FROM campaigns "
    "WHERE restaurant_id = :restaurant_id AND embedding IS NOT NULL "
    "ORDER BY distance "
    "LIMIT :top_k"
)


@dataclass(frozen=True)
class SimilarReview:
    review_id: uuid.UUID
    review_text: str
    rating: int
    distance: float


@dataclass(frozen=True)
class ReviewSearchResult:
    query: str
    matches: list[SimilarReview]


@dataclass(frozen=True)
class SimilarCampaign:
    campaign_id: uuid.UUID
    copy_text: str
    distance: float


@dataclass(frozen=True)
class CampaignSearchResult:
    reference_text: str
    matches: list[SimilarCampaign]


def _format_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vector) + "]"


def _clamp_top_k(
    top_k: int | None, *, default: int = DEFAULT_TOP_K, max_value: int = MAX_TOP_K
) -> int:
    if top_k is None:
        return default
    return max(1, min(top_k, max_value))


async def _fetch_review_matches(
    restaurant_id: uuid.UUID, vector_literal: str, top_k: int
) -> list[Any]:
    async with readonly_connection() as conn:
        result = await conn.execute(
            _REVIEW_SEARCH_SQL,
            {"restaurant_id": restaurant_id, "vector_literal": vector_literal, "top_k": top_k},
        )
        return result.all()


async def _fetch_campaign_matches(
    restaurant_id: uuid.UUID, vector_literal: str, top_k: int
) -> list[Any]:
    async with readonly_connection() as conn:
        result = await conn.execute(
            _CAMPAIGN_SEARCH_SQL,
            {"restaurant_id": restaurant_id, "vector_literal": vector_literal, "top_k": top_k},
        )
        return result.all()


async def search_reviews(
    restaurant_id: uuid.UUID, query: str, top_k: int | None = None
) -> ReviewSearchResult:
    client = EmbeddingClient()
    vectors = await client.embed_texts([query])
    vector_literal = _format_vector_literal(vectors[0])
    clamped_top_k = _clamp_top_k(top_k)

    rows = await _fetch_review_matches(restaurant_id, vector_literal, clamped_top_k)
    matches = [
        SimilarReview(
            review_id=row.id, review_text=row.review_text, rating=row.rating, distance=row.distance
        )
        for row in rows
    ]
    return ReviewSearchResult(query=query, matches=matches)


async def search_similar_campaigns(
    restaurant_id: uuid.UUID, reference_text: str, top_k: int | None = None
) -> CampaignSearchResult:
    client = EmbeddingClient()
    vectors = await client.embed_texts([reference_text])
    vector_literal = _format_vector_literal(vectors[0])
    clamped_top_k = _clamp_top_k(top_k)

    rows = await _fetch_campaign_matches(restaurant_id, vector_literal, clamped_top_k)
    matches = [
        SimilarCampaign(campaign_id=row.id, copy_text=row.copy_text, distance=row.distance)
        for row in rows
    ]
    return CampaignSearchResult(reference_text=reference_text, matches=matches)
