from datetime import date, timedelta
from decimal import Decimal

from app.agent.tools.revenue_summary import get_revenue_summary
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_get_revenue_summary_zero_transactions_range(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]
    before_window_start = SEED_START_DATE - timedelta(days=30)
    before_window_end = SEED_START_DATE - timedelta(days=1)

    summary = await get_revenue_summary(golden_skillet_id, before_window_start, before_window_end)

    assert summary.total_revenue == Decimal("0")
    assert summary.transaction_count == 0
    assert summary.average_ticket == Decimal("0")
    assert summary.daily_breakdown == []


async def test_get_revenue_summary_has_data_within_seed_window(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]

    summary = await get_revenue_summary(golden_skillet_id, SEED_START_DATE, SEED_END_DATE)

    assert summary.total_revenue > Decimal("0")
    assert summary.transaction_count > 0
    assert len(summary.daily_breakdown) == SEED_WINDOW_DAYS
    assert all(isinstance(d.day, date) for d in summary.daily_breakdown)
