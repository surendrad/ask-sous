"""Cross-cutting: migration + seed compose correctly end-to-end, and the
read-only role can actually read real seeded data (not just an empty table).
"""

import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.paths import REPO_ROOT
from app.seed.seed import seed_database


async def test_migration_then_seed_composes_cleanly(admin_engine):
    # `alembic upgrade head` is idempotent (Phase 0/1 migrations already
    # applied by the time tests run) — re-running it here proves the two
    # steps compose in the same order a fresh environment would run them.
    backend_dir = Path(REPO_ROOT) / "backend"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    async with session_maker() as session:
        summary = await seed_database(session)

    assert summary["restaurants"] == 5
    assert summary["transactions"] > 0

    async with admin_engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM restaurants"))
        assert result.scalar() == 5


async def test_readonly_role_reads_real_seeded_data(admin_engine, readonly_engine):
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    async with session_maker() as session:
        await seed_database(session)

    async with readonly_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM transactions t "
                "JOIN restaurants r ON r.id = t.restaurant_id "
                "WHERE r.name = 'Golden Skillet'"
            )
        )
        count = result.scalar()

    assert count > 0
