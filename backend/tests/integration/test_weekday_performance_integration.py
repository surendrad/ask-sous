from datetime import timedelta
from decimal import Decimal

from app.agent.tools.weekday_performance import get_weekday_performance
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_get_weekday_performance_returns_all_seven_days(seeded_restaurants):
    rid = seeded_restaurants["Golden Skillet"]

    result = await get_weekday_performance(rid, SEED_START_DATE, SEED_END_DATE)

    assert len(result) == 7
    assert all(r.transaction_count > 0 for r in result)


async def test_get_weekday_performance_surfaces_golden_skillets_seeded_tuesday_slowdown(
    seeded_restaurants,
):
    # Golden Skillet has a deliberate, documented Tuesday revenue suppression
    # (docs/reference/seed-patterns.md, Pattern 1) — Tuesday should be the
    # clear lowest-revenue weekday, the exact fact a "slowest weekday"
    # question or campaign brief needs grounded correctly.
    rid = seeded_restaurants["Golden Skillet"]

    result = await get_weekday_performance(rid, SEED_START_DATE, SEED_END_DATE)

    slowest = min(result, key=lambda r: r.total_revenue)
    assert slowest.day_of_week == "Tuesday"

    other_days_avg = sum(
        r.total_revenue for r in result if r.day_of_week != "Tuesday"
    ) / 6
    assert slowest.total_revenue < other_days_avg * Decimal("0.8")
