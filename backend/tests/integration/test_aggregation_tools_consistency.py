"""Cross-tool internal-consistency guards — every number these tools return
is implicitly trusted by every other tool (and, later, the agent), so basic
"do two independently-computed paths agree" checks matter on their own.
"""

from datetime import timedelta

from app.agent.tools.period_comparison import compare_periods
from app.agent.tools.revenue_summary import get_revenue_summary
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_revenue_summary_total_equals_sum_of_daily_breakdown(seeded_restaurants):
    summary = await get_revenue_summary(
        seeded_restaurants["Golden Skillet"], SEED_START_DATE, SEED_END_DATE
    )

    assert summary.total_revenue == sum(d.revenue for d in summary.daily_breakdown)
    assert summary.transaction_count == sum(d.transaction_count for d in summary.daily_breakdown)


async def test_compare_periods_current_matches_direct_revenue_summary_call(seeded_restaurants):
    restaurant_id = seeded_restaurants["Bella Notte"]
    period_start = SEED_START_DATE + timedelta(days=10)
    period_end = period_start + timedelta(days=6)

    comparison = await compare_periods(restaurant_id, period_start, period_end)
    direct = await get_revenue_summary(restaurant_id, period_start, period_end)

    assert comparison.current_revenue == direct.total_revenue
    assert comparison.current_transaction_count == direct.transaction_count
