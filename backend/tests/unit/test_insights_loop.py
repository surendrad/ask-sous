import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.exceptions import AgentIncompleteError
from app.agent.insights import answer_question
from app.agent.llm_client import PRO_MODEL, FinalAnswer, ToolCallRequest, UserText
from app.agent.tool_registry import INSIGHTS_TOOLS

_RID = uuid.uuid4()


async def test_single_round_returns_final_answer_with_no_tool_calls():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Hello there."))

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        result = await answer_question(_RID, "hi")

    assert result.answer == "Hello there."
    assert result.tool_calls == []
    mock_client.generate_turn.assert_awaited_once()


async def test_two_round_invokes_tool_with_parsed_args_and_feeds_result_back():
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
            FinalAnswer(text="Revenue was $500."),
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
    ):
        result = await answer_question(_RID, "what was my revenue?")

    assert result.answer == "Revenue was $500."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_revenue_summary"
    fake_tool.assert_awaited_once()
    assert mock_client.generate_turn.await_count == 2


async def test_tool_error_is_caught_and_fed_back_as_error_response():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={"restaurant_id": "not-a-uuid", "start_date": "x", "end_date": "y"},
                )
            ],
            FinalAnswer(text="Sorry, I couldn't process that."),
        ]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        result = await answer_question(_RID, "what was my revenue?")

    assert result.answer == "Sorry, I couldn't process that."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].error is not None
    assert mock_client.generate_turn.await_count == 2


async def test_round_cap_exceeded_raises_agent_incomplete():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        return_value=[
            ToolCallRequest(
                name="get_revenue_summary",
                args={"restaurant_id": "not-a-uuid", "start_date": "x", "end_date": "y"},
            )
        ]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        with pytest.raises(AgentIncompleteError):
            await answer_question(_RID, "what was my revenue?")


async def test_turn_needing_four_rounds_escalates_to_pro_model():
    tool_call = [
        ToolCallRequest(
            name="get_revenue_summary",
            args={
                "restaurant_id": str(_RID),
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
        )
    ]
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[tool_call, tool_call, tool_call, FinalAnswer(text="Deep answer.")]
    )
    fake_tool = AsyncMock(return_value={"total_revenue": "500.00"})

    with (
        patch("app.agent.insights.GeminiClient", return_value=mock_client),
        patch.dict(
            "app.agent.insights.TOOL_DISPATCH",
            {
                "get_revenue_summary": SimpleNamespace(
                    func=fake_tool,
                    parse_args=lambda a: {
                        "restaurant_id": uuid.UUID(a["restaurant_id"]),
                        "start_date": a["start_date"],
                        "end_date": a["end_date"],
                    },
                )
            },
        ),
    ):
        result = await answer_question(_RID, "what was my revenue?")

    assert result.answer == "Deep answer."
    assert result.model == PRO_MODEL
    final_call_kwargs = mock_client.generate_turn.await_args_list[-1].kwargs
    assert final_call_kwargs["model"] == PRO_MODEL


async def test_deeper_analysis_keyword_escalates_single_round_turn():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Deep dive answer."))

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        result = await answer_question(_RID, "Can you give me a deep dive on last month?")

    assert result.model == PRO_MODEL
    mock_client.generate_turn.assert_awaited_once_with(
        history=[UserText("Can you give me a deep dive on last month?")],
        tools=INSIGHTS_TOOLS,
        system_instruction=mock_client.generate_turn.await_args.kwargs["system_instruction"],
        model=PRO_MODEL,
    )
