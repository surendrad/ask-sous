from datetime import date
from decimal import Decimal

from app.agent.tools.revenue_summary import DailyRevenue
from app.agent.tools.weekday_performance import _build_weekday_performance


def test_build_weekday_performance_groups_and_sums_by_weekday():
    # 2026-06-01 is a Monday, 2026-06-02 a Tuesday, 2026-06-08 the next Monday.
    rows = [
        DailyRevenue(day=date(2026, 6, 1), transaction_count=10, revenue=Decimal("100.00")),
        DailyRevenue(day=date(2026, 6, 8), transaction_count=20, revenue=Decimal("200.00")),
        DailyRevenue(day=date(2026, 6, 2), transaction_count=5, revenue=Decimal("50.00")),
    ]

    result = _build_weekday_performance(rows)

    by_name = {r.day_of_week: r for r in result}
    assert by_name["Monday"].total_revenue == Decimal("300.00")
    assert by_name["Monday"].transaction_count == 30
    assert by_name["Monday"].average_ticket == Decimal("10.00")
    assert by_name["Tuesday"].total_revenue == Decimal("50.00")
    assert by_name["Tuesday"].transaction_count == 5


def test_build_weekday_performance_always_returns_all_seven_days_in_order():
    result = _build_weekday_performance([])

    assert [r.day_of_week for r in result] == [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]


def test_build_weekday_performance_zero_transactions_is_zero_not_error():
    result = _build_weekday_performance([])

    for row in result:
        assert row.total_revenue == Decimal("0")
        assert row.transaction_count == 0
        assert row.average_ticket == Decimal("0")


def test_build_weekday_performance_missing_day_from_range_stays_zero():
    # Only Wednesday has data — every other weekday should still appear, at zero.
    rows = [DailyRevenue(day=date(2026, 6, 3), transaction_count=8, revenue=Decimal("80.00"))]

    result = _build_weekday_performance(rows)
    by_name = {r.day_of_week: r for r in result}

    assert by_name["Wednesday"].total_revenue == Decimal("80.00")
    assert by_name["Monday"].total_revenue == Decimal("0")
    assert by_name["Sunday"].transaction_count == 0
