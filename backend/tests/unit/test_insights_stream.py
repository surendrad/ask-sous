import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.exceptions import AgentIncompleteError
from app.agent.insights import AgentTurnComplete, answer_question_stream
from app.agent.llm_client import (
    FLASH_MODEL,
    PRO_MODEL,
    FinalAnswer,
    ModelToolCalls,
    TextChunk,
    ToolCallRequest,
)

_RID = uuid.uuid4()


async def _agen(events):
    for event in events:
        yield event


def _mock_client_with_streams(*round_events: list) -> AsyncMock:
    """A mock GeminiClient whose generate_turn_stream() returns the next
    round's fixture event list on each successive call."""
    mock_client = AsyncMock()

    def stream_for_round(**kwargs):
        idx = stream_for_round.calls
        stream_for_round.calls += 1
        return _agen(round_events[idx])

    stream_for_round.calls = 0
    mock_client.generate_turn_stream = stream_for_round
    return mock_client


async def test_single_round_streams_text_chunks_then_completes():
    mock_client = _mock_client_with_streams(
        [TextChunk(text="Hello "), TextChunk(text="there."), FinalAnswer(text="Hello there.")]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        events = [event async for event in answer_question_stream([_RID], "hi")]

    assert events[:2] == [TextChunk(text="Hello "), TextChunk(text="there.")]
    assert isinstance(events[-1], AgentTurnComplete)
    assert events[-1].result.answer == "Hello there."
    assert events[-1].result.tool_calls == []
    assert events[-1].result.model == FLASH_MODEL


async def test_tool_call_round_dispatches_tool_then_streams_final_answer():
    mock_client = _mock_client_with_streams(
        [
            ModelToolCalls(
                calls=[
                    ToolCallRequest(
                        name="get_revenue_summary",
                        args={
                            "restaurant_id": str(_RID),
                            "start_date": "2026-01-01",
                            "end_date": "2026-01-31",
                        },
                    )
                ]
            )
        ],
        [TextChunk(text="Revenue was $500."), FinalAnswer(text="Revenue was $500.")],
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
        events = [event async for event in answer_question_stream([_RID], "what was my revenue?")]

    fake_tool.assert_awaited_once()
    assert events[0] == TextChunk(text="Revenue was $500.")
    final = events[-1]
    assert isinstance(final, AgentTurnComplete)
    assert final.result.answer == "Revenue was $500."
    assert len(final.result.tool_calls) == 1
    assert final.result.tool_calls[0].tool_name == "get_revenue_summary"


async def test_round_cap_exceeded_raises_agent_incomplete():
    tool_call_round = [
        ModelToolCalls(
            calls=[
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={"restaurant_id": "not-a-uuid", "start_date": "x", "end_date": "y"},
                )
            ]
        )
    ]
    mock_client = _mock_client_with_streams(*([tool_call_round] * 5))

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        with pytest.raises(AgentIncompleteError):
            async for _event in answer_question_stream([_RID], "what was my revenue?"):
                pass


async def test_deeper_analysis_keyword_escalates_to_pro():
    mock_client = _mock_client_with_streams(
        [TextChunk(text="Deep answer."), FinalAnswer(text="Deep answer.")]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        events = [
            event
            async for event in answer_question_stream([_RID], "give me a deep dive on revenue")
        ]

    assert events[-1].result.model == PRO_MODEL
