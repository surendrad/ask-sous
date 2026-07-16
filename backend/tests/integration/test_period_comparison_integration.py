from datetime import timedelta
from decimal import Decimal

from app.agent.tools.period_comparison import compare_periods
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_compare_periods_zero_transactions_both_sides(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]
    before_window = SEED_START_DATE - timedelta(days=60)

    result = await compare_periods(golden_skillet_id, before_window, before_window)

    assert result.current_revenue == Decimal("0")
    assert result.prior_revenue == Decimal("0")
    assert result.revenue_change_pct is None
