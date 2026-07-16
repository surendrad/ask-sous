"""Revenue summary tool — "how much did this restaurant make, and how many
transactions, over this date range." The base building block period_comparison
and the correctness tests in this phase reuse or mirror.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

_REVENUE_BY_DAY_SQL = text(
    "SELECT transaction_time::date AS day, COUNT(*) AS transaction_count, "
    "SUM(total_amount) AS revenue "
    "FROM transactions "
    "WHERE restaurant_id = :restaurant_id "
    "  AND transaction_time::date BETWEEN :start_date AND :end_date "
    "GROUP BY transaction_time::date "
    "ORDER BY transaction_time::date"
)


@dataclass(frozen=True)
class DailyRevenue:
    day: date
    transaction_count: int
    revenue: Decimal


@dataclass(frozen=True)
class RevenueSummary:
    restaurant_id: uuid.UUID
    start_date: date
    end_date: date
    total_revenue: Decimal
    transaction_count: int
    average_ticket: Decimal
    daily_breakdown: list[DailyRevenue]


def _summarize_daily_rows(
    restaurant_id: uuid.UUID,
    start_date: date,
    end_date: date,
    rows: Sequence[DailyRevenue],
) -> RevenueSummary:
    total_revenue = sum((row.revenue for row in rows), Decimal("0"))
    transaction_count = sum(row.transaction_count for row in rows)
    average_ticket = total_revenue / transaction_count if transaction_count > 0 else Decimal("0")
    return RevenueSummary(
        restaurant_id=restaurant_id,
        start_date=start_date,
        end_date=end_date,
        total_revenue=total_revenue,
        transaction_count=transaction_count,
        average_ticket=average_ticket,
        daily_breakdown=list(rows),
    )


async def get_revenue_summary(
    restaurant_id: uuid.UUID, start_date: date, end_date: date
) -> RevenueSummary:
    async with readonly_connection() as conn:
        result = await conn.execute(
            _REVENUE_BY_DAY_SQL,
            {"restaurant_id": restaurant_id, "start_date": start_date, "end_date": end_date},
        )
        rows = [
            DailyRevenue(day=row.day, transaction_count=row.transaction_count, revenue=row.revenue)
            for row in result.all()
        ]
    return _summarize_daily_rows(restaurant_id, start_date, end_date, rows)
