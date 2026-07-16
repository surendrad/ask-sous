"""Proves each tool built in Phase 2 actually goes through
app.agent.tools.db.readonly_connection() — not an accidentally-imported
admin session. The boundary itself (the role can't write) is already proven
by test_agent_tools_db_integration.py; this file proves this phase's
feature code actually uses that path.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from app.agent.tools import cohort_comparison, item_velocity, period_comparison, revenue_summary
from app.agent.tools.db import readonly_connection
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


def _spy_wrapping_real_connection():
    # readonly_connection() is an @asynccontextmanager — CALLING it is
    # synchronous (it returns an async context manager object); only
    # entering/exiting that object is async. A MagicMock wraps the sync
    # call correctly; an AsyncMock here would make readonly_connection()
    # return a coroutine instead of an async context manager, breaking
    # every `async with readonly_connection() as conn:` call site.
    return MagicMock(wraps=readonly_connection)


async def test_get_revenue_summary_uses_readonly_connection(seeded_restaurants):
    spy = _spy_wrapping_real_connection()
    with patch("app.agent.tools.revenue_summary.readonly_connection", spy):
        await revenue_summary.get_revenue_summary(
            seeded_restaurants["Golden Skillet"], SEED_START_DATE, SEED_END_DATE
        )
    spy.assert_called_once()


async def test_get_item_velocity_uses_readonly_connection(seeded_restaurants):
    spy = _spy_wrapping_real_connection()
    with patch("app.agent.tools.item_velocity.readonly_connection", spy):
        await item_velocity.get_item_velocity(
            seeded_restaurants["Bella Notte"], SEED_START_DATE, SEED_END_DATE
        )
    spy.assert_called_once()


async def test_compare_periods_uses_readonly_connection_twice(seeded_restaurants):
    spy = _spy_wrapping_real_connection()
    with patch("app.agent.tools.revenue_summary.readonly_connection", spy):
        await period_comparison.compare_periods(
            seeded_restaurants["Golden Skillet"], SEED_END_DATE, SEED_END_DATE
        )
    # compare_periods() calls get_revenue_summary() twice (current + prior)
    assert spy.call_count == 2


async def test_get_cohort_comparison_uses_readonly_connection(seeded_restaurants):
    spy = _spy_wrapping_real_connection()
    with patch("app.agent.tools.cohort_comparison.readonly_connection", spy):
        await cohort_comparison.get_cohort_comparison(
            seeded_restaurants["Sakura Table"], SEED_START_DATE, SEED_END_DATE
        )
    spy.assert_called_once()
