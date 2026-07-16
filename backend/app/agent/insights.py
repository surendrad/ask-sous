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
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.agent.exceptions import AgentIncompleteError
from app.agent.llm_client import (
    FLASH_MODEL,
    ConversationEntry,
    FinalAnswer,
    GeminiClient,
    ModelToolCalls,
    ToolCallRequest,
    ToolResult,
    ToolResultsTurn,
    UserText,
)
from app.agent.prompts.insights_system_instruction import build_insights_system_instruction
from app.agent.tool_registry import INSIGHTS_TOOLS, TOOL_DISPATCH, _to_jsonable

logger = structlog.get_logger()

MAX_TOOL_CALL_ROUNDS = 5


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


async def answer_question(restaurant_id: uuid.UUID, question: str) -> AgentTurnResult:
    structlog.contextvars.bind_contextvars(
        turn_id=str(uuid.uuid4()), restaurant_id=str(restaurant_id)
    )
    try:
        logger.info("agent_turn_started", question=question, restaurant_id=str(restaurant_id))
        client = GeminiClient()
        system_instruction = build_insights_system_instruction(restaurant_id)
        history: list[ConversationEntry] = [UserText(question)]
        tool_calls: list[ToolCallRecord] = []

        for _round in range(MAX_TOOL_CALL_ROUNDS):
            turn_output = await client.generate_turn(
                history=history,
                tools=INSIGHTS_TOOLS,
                system_instruction=system_instruction,
            )
            logger.info("agent_turn_model_selected", model=FLASH_MODEL)

            if isinstance(turn_output, FinalAnswer):
                if not _check_grounding(turn_output.text, tool_calls):
                    logger.warning("possible_ungrounded_numeric_answer", answer=turn_output.text)
                logger.info(
                    "agent_turn_completed",
                    answer=turn_output.text,
                    tool_call_count=len(tool_calls),
                )
                return AgentTurnResult(
                    answer=turn_output.text, tool_calls=tool_calls, model=FLASH_MODEL
                )

            history.append(ModelToolCalls(calls=turn_output))

            # Independent tool calls within a round run concurrently — each
            # hits its own DB query, so there's no reason to serialize them.
            records = await asyncio.gather(*(_run_tool_call(tc) for tc in turn_output))
            results: list[ToolResult] = []
            for record, result in records:
                logger.info(
                    "tool_call_requested", tool_name=record.tool_name, arguments=record.arguments
                )
                tool_calls.append(record)
                results.append(result)
                logger.info(
                    "tool_call_result",
                    tool_name=record.tool_name,
                    result=record.result,
                    error=record.error,
                )

            history.append(ToolResultsTurn(results=results))

        raise AgentIncompleteError(
            f"Agent did not reach a final answer within {MAX_TOOL_CALL_ROUNDS} rounds."
        )
    finally:
        structlog.contextvars.clear_contextvars()
