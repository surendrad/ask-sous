import uuid
from datetime import date
from decimal import Decimal

from app.agent.tools.revenue_summary import DailyRevenue, _summarize_daily_rows


def test_summarize_daily_rows_sums_and_averages():
    restaurant_id = uuid.uuid4()
    rows = [
        DailyRevenue(day=date(2026, 1, 1), transaction_count=2, revenue=Decimal("100.00")),
        DailyRevenue(day=date(2026, 1, 2), transaction_count=3, revenue=Decimal("150.00")),
    ]

    summary = _summarize_daily_rows(restaurant_id, date(2026, 1, 1), date(2026, 1, 2), rows)

    assert summary.total_revenue == Decimal("250.00")
    assert summary.transaction_count == 5
    assert summary.average_ticket == Decimal("250.00") / 5
    assert summary.daily_breakdown == rows


def test_summarize_daily_rows_empty_range_is_zero_not_error():
    restaurant_id = uuid.uuid4()

    summary = _summarize_daily_rows(restaurant_id, date(2026, 1, 1), date(2026, 1, 2), [])

    assert summary.total_revenue == Decimal("0")
    assert summary.transaction_count == 0
    assert summary.average_ticket == Decimal("0")
    assert summary.daily_breakdown == []


def test_summarize_daily_rows_preserves_restaurant_and_dates():
    restaurant_id = uuid.uuid4()
    start, end = date(2026, 2, 1), date(2026, 2, 28)

    summary = _summarize_daily_rows(restaurant_id, start, end, [])

    assert summary.restaurant_id == restaurant_id
    assert summary.start_date == start
    assert summary.end_date == end
