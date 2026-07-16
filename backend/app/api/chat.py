import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agent.insights import answer_question
from app.agent.tools.db import readonly_connection
from app.core.responses import error_response, success

router = APIRouter()

_RESTAURANT_EXISTS_SQL = text("SELECT 1 FROM restaurants WHERE id = :restaurant_id")


class ChatRequest(BaseModel):
    restaurant_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)


class ToolCallSummary(BaseModel):
    tool_name: str
    arguments: dict
    result: dict | None
    error: str | None


class ChatResponseData(BaseModel):
    answer: str
    tool_calls: list[ToolCallSummary]
    model: str


async def _restaurant_exists(restaurant_id: uuid.UUID) -> bool:
    async with readonly_connection() as conn:
        result = await conn.execute(_RESTAURANT_EXISTS_SQL, {"restaurant_id": restaurant_id})
        return result.first() is not None


@router.post("/chat")
async def chat(payload: ChatRequest) -> dict:
    if not await _restaurant_exists(payload.restaurant_id):
        return JSONResponse(
            status_code=404,
            content=error_response("Restaurant not found.", "restaurant_not_found"),
        )

    result = await answer_question(payload.restaurant_id, payload.question)

    data = ChatResponseData(
        answer=result.answer,
        tool_calls=[
            ToolCallSummary(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                result=tc.result,
                error=tc.error,
            )
            for tc in result.tool_calls
        ],
        model=result.model,
    )
    return success(data.model_dump())
