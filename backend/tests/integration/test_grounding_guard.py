"""Proves the test suite itself would catch a genuinely ungrounded response:
for data-requiring questions, a mocked GeminiClient scenario that jumps
straight to a FinalAnswer with a data claim and zero tool calls is asserted
to have a non-empty tool_calls list — a deliberately-broken fixture shows
that assertion actually fails when the model skips tool calls, proving the
guard's own effectiveness, not just its happy path.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.insights import answer_question
from app.agent.llm_client import FinalAnswer, ToolCallRequest

_RID = uuid.uuid4()

_DATA_REQUIRING_QUESTIONS = [
    "What was my revenue last month?",
    "Which item is trending up?",
    "How do I compare to my peers?",
]


@pytest.mark.parametrize("question", _DATA_REQUIRING_QUESTIONS)
async def test_properly_mocked_scenario_always_has_tool_calls(question, seeded_restaurants):
    restaurant_id = next(iter(seeded_restaurants.values()))
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={
                        "restaurant_id": str(restaurant_id),
                        "start_date": "2026-01-01",
                        "end_date": "2026-01-31",
                    },
                )
            ],
            FinalAnswer(text="Revenue was $500."),
        ]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        result = await answer_question(restaurant_id, question)

    assert len(result.tool_calls) > 0


@pytest.mark.parametrize("question", _DATA_REQUIRING_QUESTIONS)
async def test_zero_tool_call_scenario_fails_the_guard_assertion(question):
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Revenue was $500."))

    with pytest.raises(AssertionError):
        with patch("app.agent.insights.GeminiClient", return_value=mock_client):
            result = await answer_question(_RID, question)
        assert len(result.tool_calls) > 0
