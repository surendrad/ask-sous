from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.tools.restaurant_lookup import list_restaurants
from app.core.responses import success

router = APIRouter()


class RestaurantSummaryData(BaseModel):
    id: str
    name: str


class RestaurantListData(BaseModel):
    restaurants: list[RestaurantSummaryData]


@router.get("/restaurants")
async def get_restaurants() -> dict:
    restaurants = await list_restaurants()
    data = RestaurantListData(
        restaurants=[RestaurantSummaryData(id=str(r.id), name=r.name) for r in restaurants]
    )
    return success(data.model_dump())
