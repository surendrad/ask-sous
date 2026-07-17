import uuid
from unittest.mock import AsyncMock, patch

import pytest
import structlog

from app.agent.campaigns import generate_campaign
from app.agent.exceptions import AgentIncompleteError
from app.agent.llm_client import PRO_MODEL, FinalAnswer, ToolCallRequest
from app.agent.tool_registry import INSIGHTS_TOOLS
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
    assert result.tool_calls == []

    call_kwargs = mock_client.generate_turn.await_args.kwargs
    assert call_kwargs["model"] == PRO_MODEL
    # Agentic now — the model is offered the same tool roster chat uses,
    # even though this particular brief didn't need to call any of them.
    assert call_kwargs["tools"] == INSIGHTS_TOOLS
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
    assert completed["tool_call_count"] == 0


async def test_generate_campaign_calls_a_tool_before_writing_grounded_copy():
    # The motivating case: "create a campaign for the slowest weekday" needs
    # a real lookup before the model can write a specific day into the copy.
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        side_effect=[
            [
                ToolCallRequest(
                    name="get_weekday_performance",
                    args={
                        "restaurant_id": str(_RID),
                        "start_date": "2026-06-16",
                        "end_date": "2026-07-15",
                    },
                )
            ],
            FinalAnswer(text="Tuesdays are slow — 20% off dine-in orders over $20!"),
        ]
    )
    fake_tool = AsyncMock(
        return_value=[{"day_of_week": "Tuesday", "total_revenue": "100.00"}]
    )

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
        patch.dict(
            "app.agent.insights.TOOL_DISPATCH",
            {
                "get_weekday_performance": type(
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
        result = await generate_campaign(
            _RID, "Create a campaign for our slowest weekday, 20% off dine-in orders over $20"
        )

    assert result.copy_text == "Tuesdays are slow — 20% off dine-in orders over $20!"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_weekday_performance"
    fake_tool.assert_awaited_once()
    assert mock_client.generate_turn.await_count == 2


async def test_generate_campaign_round_cap_exceeded_raises_agent_incomplete():
    mock_client = AsyncMock()
    mock_client.generate_turn = AsyncMock(
        return_value=[
            ToolCallRequest(
                name="get_weekday_performance",
                args={
                    "restaurant_id": "not-a-uuid",
                    "start_date": "x",
                    "end_date": "y",
                },
            )
        ]
    )

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
        with pytest.raises(AgentIncompleteError):
            await generate_campaign(_RID, "Create a campaign for our slowest weekday")
