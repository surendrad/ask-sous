import uuid
from unittest.mock import AsyncMock, patch

import structlog

from app.agent.insights import answer_question
from app.agent.llm_client import FinalAnswer, ToolCallRequest

_RID = uuid.uuid4()


async def test_full_turn_emits_all_five_structured_events():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={"restaurant_id": "not-a-uuid", "start_date": "x", "end_date": "y"},
                )
            ],
            FinalAnswer(text="Here is your answer."),
        ]
    )

    with (
        patch("app.agent.insights.GeminiClient", return_value=mock_client),
        structlog.testing.capture_logs(
            processors=(structlog.contextvars.merge_contextvars,)
        ) as captured,
    ):
        await answer_question(_RID, "what was my revenue?")

    events = [entry["event"] for entry in captured]
    assert events.count("agent_turn_started") == 1
    assert events.count("tool_call_requested") == 1
    assert events.count("tool_call_result") == 1
    assert events.count("agent_turn_model_selected") == 2
    assert events.count("agent_turn_completed") == 1

    started = next(e for e in captured if e["event"] == "agent_turn_started")
    assert started["question"] == "what was my revenue?"
    assert started["restaurant_id"] == str(_RID)

    requested = next(e for e in captured if e["event"] == "tool_call_requested")
    assert requested["tool_name"] == "get_revenue_summary"
    assert requested["arguments"] == {
        "restaurant_id": "not-a-uuid",
        "start_date": "x",
        "end_date": "y",
    }

    result_event = next(e for e in captured if e["event"] == "tool_call_result")
    assert result_event["tool_name"] == "get_revenue_summary"
    assert result_event["error"] is not None

    completed = next(e for e in captured if e["event"] == "agent_turn_completed")
    assert completed["answer"] == "Here is your answer."
    assert completed["tool_call_count"] == 1


async def test_tool_call_requested_logs_parsed_args_not_raw_model_json():
    # start_date is sent as a raw JSON string by the (mocked) model; once
    # parse_args() succeeds, the logged arguments should reflect the real,
    # jsonable-serialized parsed value, not the untouched model input.
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={
                        "restaurant_id": str(_RID),
                        "start_date": "2026-01-01",
                        "end_date": "2026-01-31",
                    },
                )
            ],
            FinalAnswer(text="Answer."),
        ]
    )
    fake_tool = AsyncMock(return_value={"total_revenue": "500.00"})

    with (
        patch("app.agent.insights.GeminiClient", return_value=mock_client),
        patch.dict(
            "app.agent.insights.TOOL_DISPATCH",
            {
                "get_revenue_summary": type(
                    "Spec",
                    (),
                    {
                        "func": fake_tool,
                        "parse_args": staticmethod(
                            lambda a: {
                                "restaurant_id": uuid.UUID(a["restaurant_id"]),
                                "start_date": a["start_date"],
                                "end_date": a["end_date"],
                            }
                        ),
                    },
                )()
            },
        ),
        structlog.testing.capture_logs(
            processors=(structlog.contextvars.merge_contextvars,)
        ) as captured,
    ):
        await answer_question(_RID, "what was my revenue?")

    requested = next(e for e in captured if e["event"] == "tool_call_requested")
    # Parsed via _to_jsonable(): the UUID is stringified, not left as-is.
    assert requested["arguments"]["restaurant_id"] == str(_RID)
