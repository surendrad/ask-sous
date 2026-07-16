from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import raw_sql


async def test_run_readonly_query_counts_restaurants(seeded_restaurants):
    result = await raw_sql.run_readonly_query("SELECT COUNT(*) AS n FROM restaurants")

    assert result.row_count == 1
    assert result.rows[0]["n"] == len(seeded_restaurants)
    assert result.truncated is False


async def test_run_readonly_query_rejects_write_before_touching_db(seeded_restaurants):
    stub = AsyncMock(side_effect=AssertionError("must not reach the database"))
    with patch("app.agent.tools.raw_sql.readonly_connection", stub):
        with pytest.raises(ValueError):
            await raw_sql.run_readonly_query("DELETE FROM transactions")
    stub.assert_not_called()


async def test_run_readonly_query_truncates_at_max_rows(seeded_restaurants):
    result = await raw_sql.run_readonly_query("SELECT * FROM transaction_items", max_rows=3)

    assert result.row_count == 3
    assert result.truncated is True
