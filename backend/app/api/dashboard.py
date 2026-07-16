import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent.tools.item_velocity import get_item_velocity
from app.agent.tools.locations_comparison import compare_locations
from app.agent.tools.restaurant_lookup import list_restaurants
from app.agent.tools.revenue_summary import RevenueSummary
from app.agent.tools.upsell_metrics import UpsellMetrics, get_upsell_metrics
from app.core.responses import error_response, success

router = APIRouter()

TREND_WINDOW_DAYS = 7
TOP_ITEMS_LIMIT = 5


class DashboardKpis(BaseModel):
    total_revenue: str
    transaction_count: int
    average_ticket: str


class RevenueTrendDay(BaseModel):
    day: date
    revenue: str


class TopItem(BaseModel):
    menu_item_name: str
    total_quantity: int


class LocationDashboard(BaseModel):
    restaurant_id: uuid.UUID
    restaurant_name: str
    kpis: DashboardKpis
    revenue_trend: list[RevenueTrendDay]
    upsell_attach_rate: str


class DashboardData(BaseModel):
    locations: list[LocationDashboard]
    totals: DashboardKpis
    top_items: list[TopItem] | None


def _revenue_trend(summary: RevenueSummary, trend_days: list[date]) -> list[RevenueTrendDay]:
    revenue_by_day = {row.day: row.revenue for row in summary.daily_breakdown}
    return [
        RevenueTrendDay(day=day, revenue=str(revenue_by_day.get(day, 0))) for day in trend_days
    ]


def _totals(summaries: list[RevenueSummary]) -> DashboardKpis:
    total_revenue = sum((s.total_revenue for s in summaries), Decimal("0"))
    transaction_count = sum(s.transaction_count for s in summaries)
    average_ticket = total_revenue / transaction_count if transaction_count > 0 else Decimal("0")
    return DashboardKpis(
        total_revenue=str(total_revenue),
        transaction_count=transaction_count,
        average_ticket=str(average_ticket),
    )


@router.get("/dashboard")
async def get_dashboard(restaurant_ids: Annotated[list[uuid.UUID], Query()]) -> dict:
    restaurants = await list_restaurants()
    name_by_id = {r.id: r.name for r in restaurants}
    if not all(rid in name_by_id for rid in restaurant_ids):
        return JSONResponse(
            status_code=404,
            content=error_response("Restaurant not found.", "restaurant_not_found"),
        )

    end_date = date.today()
    start_date = end_date - timedelta(days=TREND_WINDOW_DAYS - 1)
    trend_days = [start_date + timedelta(days=i) for i in range(TREND_WINDOW_DAYS)]

    summaries, upsell_metrics = await asyncio.gather(
        compare_locations(restaurant_ids, start_date, end_date),
        get_upsell_metrics(restaurant_ids, start_date, end_date),
    )
    upsell_by_id: dict[uuid.UUID, UpsellMetrics] = {
        m.restaurant_id: m for m in upsell_metrics
    }

    locations = [
        LocationDashboard(
            restaurant_id=summary.restaurant_id,
            restaurant_name=name_by_id[summary.restaurant_id],
            kpis=DashboardKpis(
                total_revenue=str(summary.total_revenue),
                transaction_count=summary.transaction_count,
                average_ticket=str(summary.average_ticket),
            ),
            revenue_trend=_revenue_trend(summary, trend_days),
            upsell_attach_rate=str(upsell_by_id[summary.restaurant_id].attach_rate),
        )
        for summary in summaries
    ]

    top_items: list[TopItem] | None = None
    if len(restaurant_ids) == 1:
        velocities = await get_item_velocity(restaurant_ids[0], start_date, end_date)
        top_velocities = sorted(velocities, key=lambda v: v.total_quantity, reverse=True)[
            :TOP_ITEMS_LIMIT
        ]
        top_items = [
            TopItem(menu_item_name=v.menu_item_name, total_quantity=v.total_quantity)
            for v in top_velocities
        ]

    data = DashboardData(locations=locations, totals=_totals(summaries), top_items=top_items)
    return success(data.model_dump(mode="json"))
