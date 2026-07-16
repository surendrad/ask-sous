"""The insights Q&A orchestration loop — the core of Phase 3. Drives the
model through function-calling rounds against the five insights tools until
it produces a final answer, or gives up after MAX_TOOL_CALL_ROUNDS.

Grounding & audit logging (CLAUDE.md's "every agent turn logs..." rule and
"no naked numbers" rule) is embedded directly in this loop — see
docs/plans/phase-3-agent-core.md §3.2.
"""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.agent.exceptions import AgentIncompleteError
from app.agent.llm_client import (
    FLASH_MODEL,
    PRO_MODEL,
    ConversationEntry,
    FinalAnswer,
    GeminiClient,
    ModelToolCalls,
    TextChunk,
    ToolCallRequest,
    ToolResult,
    ToolResultsTurn,
    UserText,
)
from app.agent.prompts.insights_system_instruction import build_insights_system_instruction
from app.agent.tool_registry import INSIGHTS_TOOLS, TOOL_DISPATCH, _to_jsonable
from app.agent.tools.restaurant_lookup import get_restaurant_names

logger = structlog.get_logger()

MAX_TOOL_CALL_ROUNDS = 5

# See docs/decisions/010-model-routing-heuristic.md
ESCALATION_TOOL_CALL_THRESHOLD = 3
_DEEPER_ANALYSIS_KEYWORDS = ("deep dive", "deeper analysis", "thorough", "in depth", "in-depth")


def _select_model(question: str, *, completed_tool_call_rounds: int) -> tuple[str, str]:
    """Returns (model, routing_reason). A question requesting deeper
    analysis escalates immediately regardless of round count; otherwise a
    turn stays on Flash until it's needed 3+ tool-call rounds without
    reaching a final answer."""
    lowered = question.lower()
    if any(keyword in lowered for keyword in _DEEPER_ANALYSIS_KEYWORDS):
        return PRO_MODEL, "keyword"
    if completed_tool_call_rounds >= ESCALATION_TOOL_CALL_THRESHOLD:
        return PRO_MODEL, "tool_call_threshold"
    return FLASH_MODEL, "default"


@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    result: Any | None
    error: str | None


@dataclass(frozen=True)
class AgentTurnResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model: str = FLASH_MODEL


def _check_grounding(answer: str, tool_calls: list[ToolCallRecord]) -> bool:
    """Best-effort signal, not a guarantee — see docs/plans/phase-3-agent-core.md §3.2.

    Returns False (possibly ungrounded) only when the answer contains a
    digit and no tool was called this turn at all.
    """
    has_digit = bool(re.search(r"\d", answer))
    return not (has_digit and not tool_calls)


async def _run_tool_call(tool_call: ToolCallRequest) -> tuple[ToolCallRecord, ToolResult]:
    spec = TOOL_DISPATCH.get(tool_call.name)
    if spec is None:
        error = f"Unknown tool {tool_call.name!r}"
        return (
            ToolCallRecord(tool_call.name, tool_call.args, None, error),
            ToolResult(tool_name=tool_call.name, error=error),
        )

    try:
        parsed_args = spec.parse_args(tool_call.args)
        raw_result = await spec.func(**parsed_args)
        jsonable = _to_jsonable(raw_result)
        record = ToolCallRecord(tool_call.name, _to_jsonable(parsed_args), jsonable, None)
        result = ToolResult(tool_name=tool_call.name, result=jsonable)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: fed back to the model, not swallowed
        error = str(exc)
        record = ToolCallRecord(tool_call.name, tool_call.args, None, error)
        result = ToolResult(tool_name=tool_call.name, error=error)

    return record, result


async def _resolve_tool_call_round(
    calls: list[ToolCallRequest],
    history: list[ConversationEntry],
    tool_calls: list[ToolCallRecord],
) -> None:
    """Shared by answer_question() and answer_question_stream(): dispatches
    a round's tool calls concurrently, logs each request/result, and
    appends both the model's tool-call turn and the results turn to
    history — mutates `history`/`tool_calls` in place since both callers
    already own and thread those through their own loops."""
    history.append(ModelToolCalls(calls=calls))

    # Independent tool calls within a round run concurrently — each hits
    # its own DB query, so there's no reason to serialize them.
    records = await asyncio.gather(*(_run_tool_call(tc) for tc in calls))
    results: list[ToolResult] = []
    for record, result in records:
        logger.info("tool_call_requested", tool_name=record.tool_name, arguments=record.arguments)
        tool_calls.append(record)
        results.append(result)
        logger.info(
            "tool_call_result", tool_name=record.tool_name, result=record.result, error=record.error
        )

    history.append(ToolResultsTurn(results=results))


async def answer_question(restaurant_ids: list[uuid.UUID], question: str) -> AgentTurnResult:
    restaurant_id_strs = [str(r) for r in restaurant_ids]
    structlog.contextvars.bind_contextvars(
        turn_id=str(uuid.uuid4()), restaurant_ids=restaurant_id_strs
    )
    try:
        logger.info("agent_turn_started", question=question, restaurant_ids=restaurant_id_strs)
        client = GeminiClient()
        restaurant_names = await get_restaurant_names(restaurant_ids)
        system_instruction = build_insights_system_instruction(
            restaurant_ids, restaurant_names=restaurant_names
        )
        history: list[ConversationEntry] = [UserText(question)]
        tool_calls: list[ToolCallRecord] = []

        for round_index in range(MAX_TOOL_CALL_ROUNDS):
            model, routing_reason = _select_model(question, completed_tool_call_rounds=round_index)
            turn_output = await client.generate_turn(
                history=history,
                tools=INSIGHTS_TOOLS,
                system_instruction=system_instruction,
                model=model,
            )
            logger.info("agent_turn_model_selected", model=model, routing_reason=routing_reason)

            if isinstance(turn_output, FinalAnswer):
                if not _check_grounding(turn_output.text, tool_calls):
                    logger.warning("possible_ungrounded_numeric_answer", answer=turn_output.text)
                logger.info(
                    "agent_turn_completed",
                    answer=turn_output.text,
                    tool_call_count=len(tool_calls),
                )
                return AgentTurnResult(answer=turn_output.text, tool_calls=tool_calls, model=model)

            await _resolve_tool_call_round(turn_output, history, tool_calls)

        raise AgentIncompleteError(
            f"Agent did not reach a final answer within {MAX_TOOL_CALL_ROUNDS} rounds."
        )
    finally:
        structlog.contextvars.clear_contextvars()


@dataclass(frozen=True)
class AgentTurnComplete:
    """Terminal event of answer_question_stream() — carries the same
    AgentTurnResult answer_question() returns directly, so the caller can
    log/serve the full assembled response after the stream completes (the
    Risk Register's mitigation for streamed audit logging)."""

    result: AgentTurnResult


async def answer_question_stream(
    restaurant_ids: list[uuid.UUID], question: str
) -> AsyncIterator[TextChunk | AgentTurnComplete]:
    """Same orchestration as answer_question() — model routing, tool
    dispatch, grounding check, audit logging — but yields TextChunk events
    as a final-answer round's text arrives instead of returning once,
    terminating with a single AgentTurnComplete."""
    restaurant_id_strs = [str(r) for r in restaurant_ids]
    structlog.contextvars.bind_contextvars(
        turn_id=str(uuid.uuid4()), restaurant_ids=restaurant_id_strs
    )
    try:
        logger.info("agent_turn_started", question=question, restaurant_ids=restaurant_id_strs)
        client = GeminiClient()
        restaurant_names = await get_restaurant_names(restaurant_ids)
        system_instruction = build_insights_system_instruction(
            restaurant_ids, restaurant_names=restaurant_names
        )
        history: list[ConversationEntry] = [UserText(question)]
        tool_calls: list[ToolCallRecord] = []

        for round_index in range(MAX_TOOL_CALL_ROUNDS):
            model, routing_reason = _select_model(question, completed_tool_call_rounds=round_index)
            round_result: FinalAnswer | ModelToolCalls | None = None
            async for event in client.generate_turn_stream(
                history=history,
                tools=INSIGHTS_TOOLS,
                system_instruction=system_instruction,
                model=model,
            ):
                if isinstance(event, TextChunk):
                    yield event
                else:
                    round_result = event
            logger.info("agent_turn_model_selected", model=model, routing_reason=routing_reason)

            if isinstance(round_result, FinalAnswer):
                if not _check_grounding(round_result.text, tool_calls):
                    logger.warning("possible_ungrounded_numeric_answer", answer=round_result.text)
                logger.info(
                    "agent_turn_completed",
                    answer=round_result.text,
                    tool_call_count=len(tool_calls),
                )
                yield AgentTurnComplete(
                    AgentTurnResult(answer=round_result.text, tool_calls=tool_calls, model=model)
                )
                return

            if not isinstance(round_result, ModelToolCalls):
                # generate_turn_stream() always terminates a round with
                # exactly one of FinalAnswer/ModelToolCalls — anything else
                # is an SDK/adapter contract violation, not a recoverable
                # runtime state.
                raise RuntimeError(
                    "generate_turn_stream() ended a round without a terminal event: "
                    f"{round_result!r}"
                )
            await _resolve_tool_call_round(round_result.calls, history, tool_calls)

        raise AgentIncompleteError(
            f"Agent did not reach a final answer within {MAX_TOOL_CALL_ROUNDS} rounds."
        )
    finally:
        structlog.contextvars.clear_contextvars()
