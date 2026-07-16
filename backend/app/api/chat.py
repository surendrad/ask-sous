import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.insights import answer_question
from app.agent.tools.restaurant_lookup import restaurant_exists
from app.core.responses import error_response, success

router = APIRouter()


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


@router.post("/chat")
async def chat(payload: ChatRequest) -> dict:
    if not await restaurant_exists(payload.restaurant_id):
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
