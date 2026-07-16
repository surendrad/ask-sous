import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.agent.tools.period_comparison import _compare, _prior_period
from app.agent.tools.revenue_summary import RevenueSummary


def test_prior_period_single_day():
    day = date(2026, 3, 10)  # a Tuesday

    prior_start, prior_end = _prior_period(day, day)

    assert prior_start == prior_end == day - timedelta(days=1)


def test_prior_period_seven_days():
    start, end = date(2026, 3, 9), date(2026, 3, 15)  # Mon-Sun, 7 days

    prior_start, prior_end = _prior_period(start, end)

    assert prior_end == start - timedelta(days=1)
    assert (prior_end - prior_start).days == 6  # also 7 days, inclusive
    assert (end - start).days == (prior_end - prior_start).days


def test_prior_period_arbitrary_dates_not_assumed_monday_start():
    start, end = date(2026, 5, 14), date(2026, 5, 20)  # Thursday-Wednesday

    prior_start, prior_end = _prior_period(start, end)

    assert prior_end == date(2026, 5, 13)
    assert prior_start == date(2026, 5, 7)


def _summary(restaurant_id, start, end, total_revenue, transaction_count):
    average_ticket = (
        Decimal(total_revenue) / transaction_count if transaction_count else Decimal("0")
    )
    return RevenueSummary(
        restaurant_id=restaurant_id,
        start_date=start,
        end_date=end,
        total_revenue=Decimal(total_revenue),
        transaction_count=transaction_count,
        average_ticket=average_ticket,
        daily_breakdown=[],
    )


def test_compare_computes_pct_change_for_increase():
    rid = uuid.uuid4()
    current = _summary(rid, date(2026, 3, 10), date(2026, 3, 10), "150.00", 10)
    prior = _summary(rid, date(2026, 3, 9), date(2026, 3, 9), "100.00", 8)

    result = _compare(rid, current, prior)

    assert result.revenue_change_pct == Decimal("50")


def test_compare_computes_pct_change_for_decrease():
    rid = uuid.uuid4()
    current = _summary(rid, date(2026, 3, 10), date(2026, 3, 10), "50.00", 5)
    prior = _summary(rid, date(2026, 3, 9), date(2026, 3, 9), "100.00", 8)

    result = _compare(rid, current, prior)

    assert result.revenue_change_pct == Decimal("-50")


def test_compare_zero_prior_revenue_gives_none_not_zerodivisionerror():
    rid = uuid.uuid4()
    current = _summary(rid, date(2026, 3, 10), date(2026, 3, 10), "50.00", 5)
    prior = _summary(rid, date(2026, 3, 9), date(2026, 3, 9), "0", 0)

    result = _compare(rid, current, prior)

    assert result.revenue_change_pct is None


def test_compare_preserves_dates_from_inputs():
    rid = uuid.uuid4()
    current = _summary(rid, date(2026, 3, 10), date(2026, 3, 10), "50.00", 5)
    prior = _summary(rid, date(2026, 3, 9), date(2026, 3, 9), "40.00", 4)

    result = _compare(rid, current, prior)

    assert result.current_start == date(2026, 3, 10)
    assert result.current_end == date(2026, 3, 10)
    assert result.prior_start == date(2026, 3, 9)
    assert result.prior_end == date(2026, 3, 9)
