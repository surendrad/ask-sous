from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.models import Campaign, Review
from app.seed.embed_seed_data import embed_and_store_campaigns, embed_and_store_reviews

EMBEDDING_DIMENSIONS = 768


def _fake_embedding_client() -> MagicMock:
    client = MagicMock()

    async def embed_texts(texts, model="text-embedding-004"):
        return [[float(i)] * EMBEDDING_DIMENSIONS for i in range(len(texts))]

    client.embed_texts = AsyncMock(side_effect=embed_texts)
    return client


async def test_embed_and_store_reviews_updates_all_seeded_reviews(
    admin_engine: AsyncEngine, seeded_restaurants
):
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    client = _fake_embedding_client()

    async with session_maker() as session:
        updated = await embed_and_store_reviews(session, client)

    async with admin_engine.connect() as conn:
        result = await conn.execute(select(func.count()).select_from(Review))
        total = result.scalar_one()
        result = await conn.execute(
            select(func.count()).select_from(Review).where(Review.embedding.is_not(None))
        )
        non_null = result.scalar_one()

    assert updated == total
    assert non_null == total


async def test_embed_and_store_campaigns_updates_all_seeded_campaigns(
    admin_engine: AsyncEngine, seeded_restaurants
):
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    client = _fake_embedding_client()

    async with session_maker() as session:
        updated = await embed_and_store_campaigns(session, client)

    async with admin_engine.connect() as conn:
        result = await conn.execute(select(func.count()).select_from(Campaign))
        total = result.scalar_one()

    assert updated == total


async def test_embed_and_store_reviews_is_idempotent(admin_engine: AsyncEngine, seeded_restaurants):
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    client = _fake_embedding_client()

    async with session_maker() as session:
        await embed_and_store_reviews(session, client)

    async with admin_engine.connect() as conn:
        result = await conn.execute(select(Review.id, Review.embedding).order_by(Review.id))
        first_pass = {row.id: list(row.embedding) for row in result.all()}

    async with session_maker() as session:
        await embed_and_store_reviews(session, client)

    async with admin_engine.connect() as conn:
        result = await conn.execute(select(Review.id, Review.embedding).order_by(Review.id))
        second_pass = {row.id: list(row.embedding) for row in result.all()}

    assert first_pass == second_pass


def test_embed_seed_data_never_imports_readonly_connection():
    import app.seed.embed_seed_data as module

    assert "readonly_connection" not in vars(module)
