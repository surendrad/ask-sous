import uuid
from unittest.mock import AsyncMock, patch

import structlog

from app.agent.campaigns import generate_campaign
from app.agent.llm_client import PRO_MODEL, FinalAnswer
from app.agent.tools.vector_search import CampaignSearchResult, SimilarCampaign

_RID = uuid.uuid4()


def _search_result(matches: list[SimilarCampaign]) -> CampaignSearchResult:
    return CampaignSearchResult(reference_text="brief", matches=matches)


async def test_generate_campaign_uses_pro_model_and_returns_copy():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Taco Tuesday returns!"))
    examples = [
        SimilarCampaign(campaign_id=uuid.uuid4(), copy_text="Old campaign copy.", distance=0.1)
    ]

    with (
        patch("app.agent.campaigns.GeminiClient", return_value=mock_client),
        patch(
            "app.agent.campaigns.get_brand_voice_guide",
            AsyncMock(return_value="Warm and playful."),
        ),
        patch(
            "app.agent.campaigns.search_similar_campaigns",
            AsyncMock(return_value=_search_result(examples)),
        ),
    ):
        result = await generate_campaign(_RID, "Announce our new taco special")

    assert result.copy_text == "Taco Tuesday returns!"
    assert result.model == PRO_MODEL
    assert result.brand_voice_guide == "Warm and playful."
    assert result.examples_used == examples

    call_kwargs = mock_client.generate_turn.await_args.kwargs
    assert call_kwargs["model"] == PRO_MODEL
    assert call_kwargs["tools"] == []
    assert "Warm and playful." in call_kwargs["system_instruction"]
    assert "Old campaign copy." in call_kwargs["system_instruction"]


async def test_generate_campaign_succeeds_with_no_past_examples():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Fresh copy."))

    with (
        patch("app.agent.campaigns.GeminiClient", return_value=mock_client),
        patch(
            "app.agent.campaigns.get_brand_voice_guide",
            AsyncMock(return_value="Bold and cheeky."),
        ),
        patch(
            "app.agent.campaigns.search_similar_campaigns",
            AsyncMock(return_value=_search_result([])),
        ),
    ):
        result = await generate_campaign(_RID, "Announce our new taco special")

    assert result.copy_text == "Fresh copy."
    assert result.examples_used == []


async def test_generate_campaign_emits_audit_log_events():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(return_value=FinalAnswer(text="Fresh copy."))
    examples = [
        SimilarCampaign(campaign_id=uuid.uuid4(), copy_text="Old campaign copy.", distance=0.1)
    ]

    with (
        patch("app.agent.campaigns.GeminiClient", return_value=mock_client),
        patch(
            "app.agent.campaigns.get_brand_voice_guide",
            AsyncMock(return_value="Bold and cheeky."),
        ),
        patch(
            "app.agent.campaigns.search_similar_campaigns",
            AsyncMock(return_value=_search_result(examples)),
        ),
        structlog.testing.capture_logs(
            processors=(structlog.contextvars.merge_contextvars,)
        ) as captured,
    ):
        await generate_campaign(_RID, "Announce our new taco special")

    events = [entry["event"] for entry in captured]
    assert "campaign_turn_started" in events
    assert "campaign_examples_retrieved" in events
    assert "campaign_turn_completed" in events

    retrieved = next(e for e in captured if e["event"] == "campaign_examples_retrieved")
    assert retrieved["example_count"] == 1

    completed = next(e for e in captured if e["event"] == "campaign_turn_completed")
    assert completed["copy_text"] == "Fresh copy."
