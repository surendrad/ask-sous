import uuid
from datetime import date

from app.agent.prompts.campaign_system_instruction import build_campaign_system_instruction
from app.agent.tools.vector_search import SimilarCampaign

_RID = uuid.uuid4()


def test_includes_brand_voice_guide():
    instruction = build_campaign_system_instruction(_RID, "Warm, playful, family-owned.", [])
    assert "Warm, playful, family-owned." in instruction


def test_includes_both_examples_when_present():
    examples = [
        SimilarCampaign(campaign_id=uuid.uuid4(), copy_text="Taco Tuesday is back!", distance=0.1),
        SimilarCampaign(
            campaign_id=uuid.uuid4(), copy_text="Happy hour, happier you.", distance=0.2
        ),
    ]
    instruction = build_campaign_system_instruction(_RID, "Bold and cheeky.", examples)

    assert "Taco Tuesday is back!" in instruction
    assert "Happy hour, happier you." in instruction


def test_notes_absence_of_past_examples_when_empty():
    instruction = build_campaign_system_instruction(_RID, "Bold and cheeky.", [])
    assert "no past campaign examples" in instruction.lower()


def test_includes_restaurant_id_for_tool_calls():
    instruction = build_campaign_system_instruction(_RID, "Bold and cheeky.", [])
    assert str(_RID) in instruction


def test_includes_todays_date_for_relative_date_briefs():
    instruction = build_campaign_system_instruction(
        _RID, "Bold and cheeky.", [], today=date(2026, 7, 16)
    )
    assert "2026-07-16" in instruction


def test_defaults_todays_date_to_real_today():
    instruction = build_campaign_system_instruction(_RID, "Bold and cheeky.", [])
    assert date.today().isoformat() in instruction


def test_instructs_grounding_data_claims_via_tools():
    instruction = build_campaign_system_instruction(_RID, "Bold and cheeky.", [])
    assert "get_weekday_performance" in instruction
    # The core grounding rule this whole feature exists for: a data-dependent
    # claim in the brief must be looked up, not invented.
    assert "never invent" in instruction.lower() or "never guess" in instruction.lower()
