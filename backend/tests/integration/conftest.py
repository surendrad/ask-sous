import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.agent.tools.db import readonly_database_url
from app.core.config import get_settings
from app.seed.generators import RESTAURANT_PROFILES
from app.seed.seed import seed_database


@pytest_asyncio.fixture
async def admin_engine() -> AsyncEngine:
    """Engine using the same admin credentials migrations run under.

    Function-scoped (not module-scoped) deliberately: asyncpg connections
    are bound to the event loop they were created in, and pytest-asyncio
    uses a fresh event loop per test function by default, so a
    module-scoped engine breaks on the second test with "another operation
    is in progress" / cross-loop errors.
    """
    engine = create_async_engine(get_settings().database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def readonly_engine() -> AsyncEngine:
    """Engine authenticated as the dedicated read-only role (`ask_sous_readonly`).

    Points at the same database, host, and port as admin_engine — only the
    role differs. URL built by the same production code (app.agent.tools.db)
    every real tool uses, not a second hand-rolled copy of that logic.
    """
    engine = create_async_engine(readonly_database_url())
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_restaurants(admin_engine: AsyncEngine) -> dict[str, uuid.UUID]:
    """Re-seeds the database and returns {restaurant_name: id} for all five.

    Every Phase 2 tool integration test depends on this instead of each
    re-seeding and re-querying restaurant ids independently.
    """
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    async with session_maker() as session:
        await seed_database(session)

    async with admin_engine.connect() as conn:
        result = await conn.execute(text("SELECT id, name FROM restaurants"))
        by_name = {name: id_ for id_, name in result.all()}

    assert set(by_name.keys()) == {p["name"] for p in RESTAURANT_PROFILES}
    return by_name
