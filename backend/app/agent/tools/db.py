"""The only module in app/agent/ permitted to open a database connection.

Every aggregation tool (this phase) and, from Phase 3 onward, the raw SQL
tool and pgvector search tool go through readonly_connection() and nothing
else — this is the concrete implementation of the read-only boundary
described in CLAUDE.md and docs/decisions/002-readonly-postgres-role.md.

A fresh AsyncEngine is created and disposed per call rather than cached at
module scope — see docs/decisions/005-readonly-tool-connection-lifecycle.md
for why (asyncpg connections are bound to the event loop they were created
on; a cached engine risks the same cross-loop failure Phase 0 already hit
and reverted once with a module-scoped test fixture).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.config import READONLY_DB_ROLE, get_settings


def readonly_database_url() -> str:
    """The ask_sous_readonly connection URL — same host/port/database as the
    admin DATABASE_URL, with only the username/password swapped."""
    settings = get_settings()
    admin_url = make_url(settings.database_url)
    readonly_url = admin_url.set(username=READONLY_DB_ROLE, password=settings.readonly_db_password)
    return readonly_url.render_as_string(hide_password=False)


@asynccontextmanager
async def readonly_connection() -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(readonly_database_url())
    try:
        async with engine.connect() as connection:
            yield connection
    finally:
        await engine.dispose()
