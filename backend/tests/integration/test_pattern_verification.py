"""Proves each Phase 2 aggregation tool correctly detects the exact
deliberate patterns documented in docs/reference/seed-patterns.md. Every
threshold here uses a safety margin BELOW the documented actual figure, so
these tests stay robust to the seed generator's small amount of Gaussian
noise without ever contradicting the published numbers. If a threshold ever
flakes, the fix is to widen the margin (or pick a less boundary-adjacent
date), never to lower the bar.
"""

from datetime import timedelta
from decimal import Decimal

from app.agent.tools.cohort_comparison import get_cohort_comparison
from app.agent.tools.item_velocity import get_item_velocity
from app.agent.tools.period_comparison import compare_periods
from app.agent.tools.revenue_summary import get_revenue_summary
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS, TRUFFLE_FRIES_ITEM_NAME

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)
TUESDAY = 1  # Python's date.weekday(): Monday=0 ... Sunday=6


def _tuesday_vs_other_days_avg(daily_breakdown):
    tuesdays = [d.revenue for d in daily_breakdown if d.day.weekday() == TUESDAY]
    others = [d.revenue for d in daily_breakdown if d.day.weekday() != TUESDAY]
    tuesday_avg = sum(tuesdays) / len(tuesdays)
    other_avg = sum(others) / len(others)
    return tuesday_avg, other_avg


async def test_golden_skillet_tuesday_slowdown_via_revenue_summary(seeded_restaurants):
    summary = await get_revenue_summary(
        seeded_restaurants["Golden Skillet"], SEED_START_DATE, SEED_END_DATE
    )

    tuesday_avg, other_avg = _tuesday_vs_other_days_avg(summary.daily_breakdown)

    # Documented actual gap: ~57.7% below. Margin: assert at least 40% below.
    assert tuesday_avg <= other_avg * Decimal("0.60")


async def test_golden_skillet_tuesday_slowdown_via_compare_periods(seeded_restaurants):
    # A Tuesday well inside the window, so its prior Monday is also inside it.
    a_tuesday = SEED_START_DATE + timedelta(days=33)
    assert a_tuesday.weekday() == TUESDAY, "fixture date drifted — adjust offset"

    result = await compare_periods(seeded_restaurants["Golden Skillet"], a_tuesday, a_tuesday)

    assert result.prior_start == result.prior_end == a_tuesday - timedelta(days=1)
    # Documented multiplier gap suggests ~50% below Monday; single-day
    # comparisons carry more noise than a 90-day average, so use a more
    # conservative -25% floor here.
    assert result.revenue_change_pct <= Decimal("-25")


async def test_casa_verde_control_tuesday_is_not_suppressed(seeded_restaurants):
    summary = await get_revenue_summary(
        seeded_restaurants["Casa Verde"], SEED_START_DATE, SEED_END_DATE
    )

    tuesday_avg, other_avg = _tuesday_vs_other_days_avg(summary.daily_breakdown)

    assert tuesday_avg >= other_avg * Decimal("0.80")


async def test_bella_notte_truffle_fries_trend_via_item_velocity_halves(seeded_restaurants):
    velocities = await get_item_velocity(
        seeded_restaurants["Bella Notte"],
        SEED_START_DATE,
        SEED_END_DATE,
        menu_item_name=TRUFFLE_FRIES_ITEM_NAME,
    )

    assert len(velocities) == 1
    v = velocities[0]
    assert v.trend == "up"
    # Even 45/45 halves split predicts ~2.2x (different from seed-patterns.md's
    # first/last-30-with-middle-excluded ~3.0x figure — both correct, see
    # docs/decisions for why they differ). Margin: assert at least 1.7x.
    assert v.second_half_quantity >= Decimal("1.7") * v.first_half_quantity


async def test_bella_notte_truffle_fries_trend_matches_seed_patterns_methodology(
    seeded_restaurants,
):
    bella_notte_id = seeded_restaurants["Bella Notte"]
    first_30_end = SEED_START_DATE + timedelta(days=29)
    last_30_start = SEED_END_DATE - timedelta(days=29)

    first_30 = await get_item_velocity(
        bella_notte_id, SEED_START_DATE, first_30_end, menu_item_name=TRUFFLE_FRIES_ITEM_NAME
    )
    last_30 = await get_item_velocity(
        bella_notte_id, last_30_start, SEED_END_DATE, menu_item_name=TRUFFLE_FRIES_ITEM_NAME
    )

    first_30_total = first_30[0].total_quantity if first_30 else 0
    last_30_total = last_30[0].total_quantity if last_30 else 0

    # Direct cross-check against seed-patterns.md's documented 363 -> 1,096 (~3.0x).
    assert last_30_total >= 2 * first_30_total


async def test_sakura_table_premium_ticket_via_cohort_comparison(seeded_restaurants):
    result = await get_cohort_comparison(
        seeded_restaurants["Sakura Table"],
        SEED_START_DATE,
        SEED_END_DATE,
        metric="average_ticket",
    )

    # Documented actual: ~2.1x. implementation-plan.md's bar: "at least 1.3x".
    assert result.ratio_to_peers >= Decimal("1.5")


async def test_cohort_comparison_control_contrast(seeded_restaurants):
    sakura = await get_cohort_comparison(
        seeded_restaurants["Sakura Table"], SEED_START_DATE, SEED_END_DATE
    )
    golden_skillet = await get_cohort_comparison(
        seeded_restaurants["Golden Skillet"], SEED_START_DATE, SEED_END_DATE
    )

    # Not asserted "close to 1.0" — Golden Skillet's peer group still
    # includes Sakura Table, which pulls its own peer average up. Only the
    # contrast between the two ratios is the meaningful, non-circular claim.
    assert golden_skillet.ratio_to_peers < Decimal("1.3")
    assert sakura.ratio_to_peers > golden_skillet.ratio_to_peers


async def test_cohort_comparison_total_revenue_metric_sanity(seeded_restaurants):
    result = await get_cohort_comparison(
        seeded_restaurants["Harbor & Vine"],
        SEED_START_DATE,
        SEED_END_DATE,
        metric="total_revenue",
    )

    assert result.restaurant_value >= Decimal("0")
    assert result.peer_value >= Decimal("0")
    assert result.peer_restaurant_count == 4


async def test_cohort_comparison_transaction_count_metric_sanity(seeded_restaurants):
    result = await get_cohort_comparison(
        seeded_restaurants["Casa Verde"],
        SEED_START_DATE,
        SEED_END_DATE,
        metric="transaction_count",
    )

    assert result.restaurant_value >= Decimal("0")
    assert result.peer_value >= Decimal("0")
    assert result.peer_restaurant_count == 4
