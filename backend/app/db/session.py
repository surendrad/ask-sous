from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a database session.

    Not consumed by any route yet (Phase 0 has no data-backed endpoints) —
    this establishes the pattern Phase 1's routes will use.
    """
    async with async_session_maker() as session:
        yield session
