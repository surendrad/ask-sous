"""Period comparison tool — "how did this period do against the period right
before it." A single mechanism handles day-over-day (a 1-day period) and
week-over-week (a 7-day period) as the same thing at different granularities.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.agent.tools.revenue_summary import RevenueSummary, get_revenue_summary


@dataclass(frozen=True)
class PeriodComparison:
    restaurant_id: uuid.UUID
    current_start: date
    current_end: date
    current_revenue: Decimal
    current_transaction_count: int
    prior_start: date
    prior_end: date
    prior_revenue: Decimal
    prior_transaction_count: int
    revenue_change_pct: Decimal | None


def _prior_period(period_start: date, period_end: date) -> tuple[date, date]:
    period_length = (period_end - period_start).days + 1
    prior_end = period_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=period_length - 1)
    return prior_start, prior_end


def _compare(
    restaurant_id: uuid.UUID, current: RevenueSummary, prior: RevenueSummary
) -> PeriodComparison:
    revenue_change_pct = (
        (current.total_revenue - prior.total_revenue) / prior.total_revenue * 100
        if prior.total_revenue > 0
        else None
    )
    return PeriodComparison(
        restaurant_id=restaurant_id,
        current_start=current.start_date,
        current_end=current.end_date,
        current_revenue=current.total_revenue,
        current_transaction_count=current.transaction_count,
        prior_start=prior.start_date,
        prior_end=prior.end_date,
        prior_revenue=prior.total_revenue,
        prior_transaction_count=prior.transaction_count,
        revenue_change_pct=revenue_change_pct,
    )


async def compare_periods(
    restaurant_id: uuid.UUID, period_start: date, period_end: date
) -> PeriodComparison:
    prior_start, prior_end = _prior_period(period_start, period_end)
    current = await get_revenue_summary(restaurant_id, period_start, period_end)
    prior = await get_revenue_summary(restaurant_id, prior_start, prior_end)
    return _compare(restaurant_id, current, prior)
