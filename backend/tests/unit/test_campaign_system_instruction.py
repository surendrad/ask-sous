import uuid

from app.agent.prompts.campaign_system_instruction import build_campaign_system_instruction
from app.agent.tools.vector_search import SimilarCampaign


def test_includes_brand_voice_guide():
    instruction = build_campaign_system_instruction("Warm, playful, family-owned.", [])
    assert "Warm, playful, family-owned." in instruction


def test_includes_both_examples_when_present():
    examples = [
        SimilarCampaign(campaign_id=uuid.uuid4(), copy_text="Taco Tuesday is back!", distance=0.1),
        SimilarCampaign(
            campaign_id=uuid.uuid4(), copy_text="Happy hour, happier you.", distance=0.2
        ),
    ]
    instruction = build_campaign_system_instruction("Bold and cheeky.", examples)

    assert "Taco Tuesday is back!" in instruction
    assert "Happy hour, happier you." in instruction


def test_notes_absence_of_past_examples_when_empty():
    instruction = build_campaign_system_instruction("Bold and cheeky.", [])
    assert "no past campaign examples" in instruction.lower()
