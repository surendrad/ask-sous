import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.campaigns import generate_campaign
from app.agent.tools.restaurant_lookup import restaurant_exists
from app.core.responses import error_response, success

router = APIRouter()


class CampaignRequest(BaseModel):
    restaurant_id: uuid.UUID
    brief: str = Field(min_length=1, max_length=2000)


class CampaignExampleSummary(BaseModel):
    campaign_id: uuid.UUID
    copy_text: str


class CampaignResponseData(BaseModel):
    copy_text: str
    examples_used: list[CampaignExampleSummary]
    model: str


@router.post("/campaigns")
async def generate_campaign_endpoint(payload: CampaignRequest) -> dict:
    if not await restaurant_exists(payload.restaurant_id):
        return JSONResponse(
            status_code=404,
            content=error_response("Restaurant not found.", "restaurant_not_found"),
        )

    result = await generate_campaign(payload.restaurant_id, payload.brief)

    data = CampaignResponseData(
        copy_text=result.copy_text,
        examples_used=[
            CampaignExampleSummary(campaign_id=example.campaign_id, copy_text=example.copy_text)
            for example in result.examples_used
        ],
        model=result.model,
    )
    return success(data.model_dump())
