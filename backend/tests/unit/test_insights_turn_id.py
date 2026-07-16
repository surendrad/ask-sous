import uuid
from unittest.mock import AsyncMock, patch

import pytest
import structlog

from app.agent.exceptions import AgentIncompleteError
from app.agent.insights import answer_question
from app.agent.llm_client import FinalAnswer, ToolCallRequest

_RID = uuid.uuid4()


async def test_all_log_events_in_a_turn_share_the_same_turn_id():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_revenue_summary",
                    args={"restaurant_id": "bad", "start_date": "x", "end_date": "y"},
                )
            ],
            FinalAnswer(text="Answer."),
        ]
    )

    with (
        patch("app.agent.insights.GeminiClient", return_value=mock_client),
        structlog.testing.capture_logs(
            processors=(structlog.contextvars.merge_contextvars,)
        ) as captured,
    ):
        await answer_question([_RID], "question")

    turn_ids = {entry["turn_id"] for entry in captured}
    assert len(turn_ids) == 1


async def test_contextvars_cleared_after_agent_incomplete_error():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        return_value=[
            ToolCallRequest(
                name="get_revenue_summary",
                args={"restaurant_id": "bad", "start_date": "x", "end_date": "y"},
            )
        ]
    )

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        with pytest.raises(AgentIncompleteError):
            await answer_question([_RID], "question")

    logger = structlog.get_logger()
    with structlog.testing.capture_logs(
        processors=(structlog.contextvars.merge_contextvars,)
    ) as captured:
        logger.info("unrelated_event_after_failed_turn")

    assert "turn_id" not in captured[0]
