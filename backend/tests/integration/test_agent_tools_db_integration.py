import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.agent.tools.db import readonly_connection
from app.core.config import READONLY_DB_ROLE


async def test_readonly_connection_reports_readonly_role():
    async with readonly_connection() as conn:
        result = await conn.execute(text("SELECT current_user"))
        assert result.scalar() == READONLY_DB_ROLE


async def test_readonly_connection_can_select():
    async with readonly_connection() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM restaurants"))
        assert result.scalar() is not None


async def test_readonly_connection_rejects_insert():
    with pytest.raises(DBAPIError, match="permission denied|InsufficientPrivilege"):
        async with readonly_connection() as conn:
            await conn.execute(text("INSERT INTO restaurants (name) VALUES ('test')"))
