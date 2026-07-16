import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@pytest_asyncio.fixture
async def probe_table(admin_engine):
    """A throwaway table, created by the admin role, dropped after the test.

    Used to prove the readonly role can read objects it didn't create itself
    (via ALTER DEFAULT PRIVILEGES) and cannot write to them.
    """
    async with admin_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS _readonly_probe"))
        await conn.execute(text("CREATE TABLE _readonly_probe (id int)"))
    yield "_readonly_probe"
    async with admin_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS _readonly_probe"))
        await conn.execute(text("DROP TABLE IF EXISTS _readonly_should_fail"))


async def test_vector_extension_is_enabled(admin_engine):
    async with admin_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        assert result.scalar() == 1


async def test_readonly_role_exists_and_can_select(admin_engine, readonly_engine, probe_table):
    async with admin_engine.begin() as conn:
        await conn.execute(text("INSERT INTO _readonly_probe VALUES (1)"))

    async with readonly_engine.connect() as conn:
        result = await conn.execute(text("SELECT id FROM _readonly_probe"))
        assert result.scalar() == 1


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE _readonly_should_fail (id int)",
        "INSERT INTO _readonly_probe VALUES (99)",
        "DROP TABLE _readonly_probe",
    ],
)
async def test_readonly_role_cannot_write(readonly_engine, probe_table, statement):
    with pytest.raises(DBAPIError, match="permission denied|InsufficientPrivilege"):
        async with readonly_engine.begin() as conn:
            await conn.execute(text(statement))
