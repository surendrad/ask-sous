"""Hand-crafted vectors inserted directly into real seeded rows prove the
real pgvector <=>/ORDER BY/LIMIT/restaurant-scoping SQL works correctly —
independent of whether the vectors are semantically real embeddings.
`seeded_restaurants` re-seeds (TRUNCATE + reinsert) fresh for every test, so
no explicit teardown of these hand-crafted embeddings is needed.
"""

from unittest.mock import AsyncMock, patch

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.agent.tools import vector_search
from app.db.models import Review

_DIM = 768


def _vector(base: float) -> list[float]:
    return [base] * _DIM


async def _set_review_embedding(admin_engine: AsyncEngine, review_id, vector: list[float]) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE reviews SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": vector_search._format_vector_literal(vector), "id": review_id},
        )


async def _first_n_review_ids(admin_engine: AsyncEngine, restaurant_id, n: int) -> list:
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(
            select(Review.id).where(Review.restaurant_id == restaurant_id).limit(n)
        )
        return [row[0] for row in result.all()]


def _mock_embedding_client(query_vector: list[float]):
    fake_client = AsyncMock()
    fake_client.embed_texts = AsyncMock(return_value=[query_vector])
    return patch("app.agent.tools.vector_search.EmbeddingClient", return_value=fake_client)


async def test_search_reviews_orders_by_real_cosine_distance(admin_engine, seeded_restaurants):
    restaurant_id = seeded_restaurants["Golden Skillet"]
    ids = await _first_n_review_ids(admin_engine, restaurant_id, 3)
    assert len(ids) == 3

    identical, near, far = _vector(1.0), _vector(0.99), _vector(-1.0)
    await _set_review_embedding(admin_engine, ids[0], identical)
    await _set_review_embedding(admin_engine, ids[1], near)
    await _set_review_embedding(admin_engine, ids[2], far)

    with _mock_embedding_client(identical):
        result = await vector_search.search_reviews(restaurant_id, "query", top_k=3)

    returned_ids = [m.review_id for m in result.matches]
    assert returned_ids == [ids[0], ids[1], ids[2]]


async def test_search_reviews_scopes_to_restaurant(admin_engine, seeded_restaurants):
    golden_id = seeded_restaurants["Golden Skillet"]
    casa_id = seeded_restaurants["Casa Verde"]

    golden_review = (await _first_n_review_ids(admin_engine, golden_id, 1))[0]
    casa_review = (await _first_n_review_ids(admin_engine, casa_id, 1))[0]

    same_vector = _vector(1.0)
    await _set_review_embedding(admin_engine, golden_review, same_vector)
    await _set_review_embedding(admin_engine, casa_review, same_vector)

    with _mock_embedding_client(same_vector):
        result = await vector_search.search_reviews(golden_id, "query", top_k=5)

    returned_ids = [m.review_id for m in result.matches]
    assert golden_review in returned_ids
    assert casa_review not in returned_ids


async def test_search_reviews_with_no_embedded_rows_returns_empty_matches(
    admin_engine, seeded_restaurants
):
    restaurant_id = seeded_restaurants["Golden Skillet"]

    with _mock_embedding_client(_vector(1.0)):
        result = await vector_search.search_reviews(restaurant_id, "query", top_k=5)

    assert result.matches == []
