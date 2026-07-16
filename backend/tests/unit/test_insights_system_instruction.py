import uuid
from datetime import date
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


def test_system_instruction_includes_todays_date_for_relative_date_questions():
    # A real live call ("how much revenue in the last 7 days?") revealed the
    # model has no way to know "today" on its own — it hallucinated calling
    # nonexistent today()/timedelta() tools, then correctly declined to
    # guess rather than answer with a made-up date range. Only a real model
    # call surfaced this; mocked tests never exercise what the model
    # actually does with an ambiguous relative-date question.
    instruction = build_insights_system_instruction(_RID, today=date(2026, 7, 16))
    assert "2026-07-16" in instruction


def test_system_instruction_defaults_todays_date_to_real_today():
    instruction = build_insights_system_instruction(_RID)
    assert date.today().isoformat() in instruction
