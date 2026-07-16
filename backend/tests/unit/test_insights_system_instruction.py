import uuid
from unittest.mock import AsyncMock, patch

from app.agent.insights import answer_question
from app.agent.llm_client import FinalAnswer
from app.agent.prompts.insights_system_instruction import build_insights_system_instruction

_RID = uuid.uuid4()


async def test_system_instruction_passed_to_model_includes_restaurant_id():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Hi."))

    with patch("app.agent.insights.GeminiClient", return_value=mock_client):
        await answer_question(_RID, "hi")

    _, kwargs = mock_client.generate_turn.call_args
    assert str(_RID) in kwargs["system_instruction"]


def test_system_instruction_mentions_qualitative_review_search():
    instruction = build_insights_system_instruction(_RID)
    assert "search_customer_reviews" in instruction
