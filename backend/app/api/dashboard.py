import uuid
from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent.tools.item_velocity import get_item_velocity
from app.agent.tools.restaurant_lookup import restaurant_exists
from app.agent.tools.revenue_summary import get_revenue_summary
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


class DashboardData(BaseModel):
    kpis: DashboardKpis
    revenue_trend: list[RevenueTrendDay]
    top_items: list[TopItem]


@router.get("/dashboard")
async def get_dashboard(restaurant_id: uuid.UUID) -> dict:
    if not await restaurant_exists(restaurant_id):
        return JSONResponse(
            status_code=404,
            content=error_response("Restaurant not found.", "restaurant_not_found"),
        )

    end_date = date.today()
    start_date = end_date - timedelta(days=TREND_WINDOW_DAYS - 1)

    revenue = await get_revenue_summary(restaurant_id, start_date, end_date)
    velocities = await get_item_velocity(restaurant_id, start_date, end_date)
    top_items = sorted(velocities, key=lambda v: v.total_quantity, reverse=True)[:TOP_ITEMS_LIMIT]

    revenue_by_day = {row.day: row.revenue for row in revenue.daily_breakdown}
    trend_days = [start_date + timedelta(days=i) for i in range(TREND_WINDOW_DAYS)]

    data = DashboardData(
        kpis=DashboardKpis(
            total_revenue=str(revenue.total_revenue),
            transaction_count=revenue.transaction_count,
            average_ticket=str(revenue.average_ticket),
        ),
        revenue_trend=[
            RevenueTrendDay(day=day, revenue=str(revenue_by_day.get(day, 0))) for day in trend_days
        ],
        top_items=[
            TopItem(menu_item_name=v.menu_item_name, total_quantity=v.total_quantity)
            for v in top_items
        ],
    )
    return success(data.model_dump(mode="json"))
