"""Populates the seeded reviews'/campaigns' `embedding` columns via Vertex
AI, as a follow-up step to `seed.py` — kept as a separate script (not
merged into seed.py) so plain seeding still works with zero GCP dependency.
Uses the same privileged session `seed.py` uses (never the read-only tool
path — this writes, and app.agent.tools.db's role can't). Run via:

    python -m app.seed.embed_seed_data
"""

import asyncio
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

from sqlalchemy import bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.embedding_client import EmbeddingClient
from app.db.models import Campaign, Review
from app.db.session import async_session_maker

BATCH_SIZE = 100


def _chunk[T](items: Sequence[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def _build_update_payloads(
    ids: Sequence[uuid.UUID], vectors: Sequence[list[float]]
) -> list[dict[str, Any]]:
    if len(ids) != len(vectors):
        raise ValueError(f"ids/vectors length mismatch: {len(ids)} ids vs {len(vectors)} vectors.")
    return [{"row_id": id_, "embedding": vector} for id_, vector in zip(ids, vectors, strict=True)]


async def _embed_and_store(
    session: AsyncSession,
    client: EmbeddingClient,
    *,
    model_class: type[Review] | type[Campaign],
    id_column,
    text_column,
) -> int:
    result = await session.execute(select(id_column, text_column))
    rows = result.all()
    if not rows:
        return 0

    ids = [row[0] for row in rows]
    texts = [row[1] for row in rows]

    total_updated = 0
    for id_batch, text_batch in zip(
        _chunk(ids, BATCH_SIZE), _chunk(texts, BATCH_SIZE), strict=True
    ):
        vectors = await client.embed_texts(text_batch)
        payloads = _build_update_payloads(id_batch, vectors)
        # Core-level update (against __table__, not the ORM entity) —
        # mirrors seed.py's own Core-level bulk inserts, and avoids the ORM
        # bulk-update path's requirement that bind param names match mapped
        # attribute keys exactly.
        await session.execute(
            update(model_class.__table__)
            .where(model_class.__table__.c.id == bindparam("row_id"))
            .values(embedding=bindparam("embedding")),
            payloads,
        )
        total_updated += len(payloads)

    await session.commit()
    return total_updated


async def embed_and_store_reviews(session: AsyncSession, client: EmbeddingClient) -> int:
    return await _embed_and_store(
        session,
        client,
        model_class=Review,
        id_column=Review.id,
        text_column=Review.review_text,
    )


async def embed_and_store_campaigns(session: AsyncSession, client: EmbeddingClient) -> int:
    return await _embed_and_store(
        session,
        client,
        model_class=Campaign,
        id_column=Campaign.id,
        text_column=Campaign.copy_text,
    )


async def main() -> None:
    client = EmbeddingClient()
    async with async_session_maker() as session:
        reviews_updated = await embed_and_store_reviews(session, client)
        campaigns_updated = await embed_and_store_campaigns(session, client)
    print(f"reviews embedded: {reviews_updated}")
    print(f"campaigns embedded: {campaigns_updated}")


if __name__ == "__main__":
    asyncio.run(main())
