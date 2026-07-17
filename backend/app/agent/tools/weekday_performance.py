"""Weekday performance tool — "which day of the week is slowest/busiest,"
grouping revenue by day-of-week rather than by individual calendar date.

Exists specifically so this grouping happens once, in code, instead of the
model reasoning over ~30 raw daily rows itself each time it's asked — see
docs/decisions/016-agentic-campaign-generation.md. Both answer_question()
(chat) and generate_campaign() (campaigns) call this same function, so a
"what was my slowest weekday" question and a "build a campaign for my
slowest weekday" brief are guaranteed to agree, not just likely to.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.agent.tools.revenue_summary import DailyRevenue, get_revenue_summary

_WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


@dataclass(frozen=True)
class WeekdayRevenue:
    day_of_week: str
    total_revenue: Decimal
    transaction_count: int
    average_ticket: Decimal


def _build_weekday_performance(daily_rows: list[DailyRevenue]) -> list[WeekdayRevenue]:
    """Always returns all seven weekdays, Monday through Sunday, even ones
    with zero activity in the given rows — so "which weekday is slowest"
    is a plain min() over a complete, fixed-length list, not a lookup that
    might be missing an entry."""
    revenue_by_index = [Decimal("0")] * 7
    count_by_index = [0] * 7
    for row in daily_rows:
        index = row.day.weekday()
        revenue_by_index[index] += row.revenue
        count_by_index[index] += row.transaction_count

    result = []
    for index, name in enumerate(_WEEKDAY_NAMES):
        total_revenue = revenue_by_index[index]
        transaction_count = count_by_index[index]
        average_ticket = (
            total_revenue / transaction_count if transaction_count > 0 else Decimal("0")
        )
        result.append(
            WeekdayRevenue(
                day_of_week=name,
                total_revenue=total_revenue,
                transaction_count=transaction_count,
                average_ticket=average_ticket,
            )
        )
    return result


async def get_weekday_performance(
    restaurant_id: uuid.UUID, start_date: date, end_date: date
) -> list[WeekdayRevenue]:
    summary = await get_revenue_summary(restaurant_id, start_date, end_date)
    return _build_weekday_performance(summary.daily_breakdown)
