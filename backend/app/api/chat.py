import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.agent.insights import AgentTurnComplete, answer_question_stream
from app.agent.llm_client import TextChunk
from app.agent.tools.restaurant_lookup import restaurant_exists
from app.core.responses import error_response

logger = structlog.get_logger()

router = APIRouter()


class ChatRequest(BaseModel):
    restaurant_ids: list[uuid.UUID] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)


class ToolCallSummary(BaseModel):
    tool_name: str
    arguments: dict
    # Most tools return a single dict, but multi-restaurant tools like
    # compare_locations()/get_upsell_metrics() return a list (one entry per
    # restaurant) — found via a live /chat call against a real multi-location
    # question, which crashed here before this type accounted for it.
    result: dict | list | None
    error: str | None


class ChatResponseData(BaseModel):
    answer: str
    tool_calls: list[ToolCallSummary]
    model: str


def _sse_frame(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _encode_event(event: TextChunk | AgentTurnComplete) -> str:
    if isinstance(event, TextChunk):
        return _sse_frame({"type": "text_chunk", "text": event.text})

    data = ChatResponseData(
        answer=event.result.answer,
        tool_calls=[
            ToolCallSummary(
                tool_name=tc.tool_name, arguments=tc.arguments, result=tc.result, error=tc.error
            )
            for tc in event.result.tool_calls
        ],
        model=event.result.model,
    )
    return _sse_frame({"type": "done", **data.model_dump()})


def _domain_error_event(exc: AgentUnavailableError | AgentIncompleteError) -> str:
    if isinstance(exc, AgentUnavailableError):
        message = "The agent is temporarily unavailable. Please try again."
        code = "agent_unavailable"
    else:
        message = "The agent couldn't complete this request. Try rephrasing your question."
        code = "agent_incomplete"
    return _sse_frame({"type": "error", "message": message, "code": code})


async def _event_stream(
    first_event: TextChunk | AgentTurnComplete, rest: AsyncIterator[TextChunk | AgentTurnComplete]
) -> AsyncIterator[str]:
    yield _encode_event(first_event)
    try:
        async for event in rest:
            yield _encode_event(event)
    except (AgentUnavailableError, AgentIncompleteError) as exc:
        # The response has already started (headers/status 200 committed),
        # so a mid-stream failure can't become a 503/502 the way a
        # before-first-chunk failure does below — it surfaces as a final
        # SSE error event instead. See docs/decisions/011.
        yield _domain_error_event(exc)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any other mid-stream
        # failure must still end the stream with a visible error event, not
        # a silent connection close the client would otherwise hang on.
        # Mirrors app.core.errors.unhandled_exception_handler's "log full
        # detail server-side, return only a generic message" shape.
        logger.error("chat_stream_unhandled_exception", exc_info=exc)
        yield _sse_frame(
            {"type": "error", "message": "An unexpected error occurred.", "code": "internal_error"}
        )


@router.post("/chat", response_model=None)
async def chat(payload: ChatRequest) -> JSONResponse | StreamingResponse:
    exists = await asyncio.gather(*(restaurant_exists(rid) for rid in payload.restaurant_ids))
    if not all(exists):
        return JSONResponse(
            status_code=404,
            content=error_response("Restaurant not found.", "restaurant_not_found"),
        )

    stream = answer_question_stream(payload.restaurant_ids, payload.question)
    # Pull the first event outside the StreamingResponse so a failure that
    # happens before anything has been sent to the client still goes
    # through the normal AgentUnavailableError/AgentIncompleteError ->
    # 503/502 JSON exception handlers, instead of being silently downgraded
    # to a mid-stream SSE error event it doesn't need to be. answer_question_stream()
    # always either yields at least one event or raises — it never returns empty.
    first_event = await anext(stream)

    return StreamingResponse(_event_stream(first_event, stream), media_type="text/event-stream")
