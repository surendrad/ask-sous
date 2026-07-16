"""Multi-location comparison tool (Phase 8) — "how do my selected
locations compare" on revenue over a date range. Reused by both the
compare_locations LLM-callable tool and the dashboard's multi-location
view, so the comparison logic is written once, not reimplemented twice.
"""

import asyncio
import uuid
from datetime import date

from app.agent.tools.revenue_summary import RevenueSummary, get_revenue_summary


async def compare_locations(
    restaurant_ids: list[uuid.UUID], start_date: date, end_date: date
) -> list[RevenueSummary]:
    """One RevenueSummary per restaurant, in the same order as
    restaurant_ids. Independent per-restaurant queries with no data
    dependency between them, so they run concurrently — same reasoning as
    the tool-call fan-out in insights.py."""
    return list(
        await asyncio.gather(
            *(get_revenue_summary(rid, start_date, end_date) for rid in restaurant_ids)
        )
    )
