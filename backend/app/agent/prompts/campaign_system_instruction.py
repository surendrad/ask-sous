"""System instruction for campaign generation — see
docs/plans/phase-5-campaign-generation.md §5.4.
"""

from app.agent.tools.vector_search import SimilarCampaign

_NO_EXAMPLES_NOTE = (
    "No past campaign examples are available for this restaurant — write "
    "from the brand voice guide alone."
)


def _format_examples(examples: list[SimilarCampaign]) -> str:
    if not examples:
        return _NO_EXAMPLES_NOTE
    return "\n\n".join(f"- {example.copy_text}" for example in examples)


def build_campaign_system_instruction(
    brand_voice_guide: str, examples: list[SimilarCampaign]
) -> str:
    return f"""You are Ask Sous, writing a marketing campaign for a restaurant.

The restaurant's brand voice guide:
{brand_voice_guide}

Past campaigns for this restaurant, for tone and style reference:
{_format_examples(examples)}

Rules:
- Write only the campaign copy itself — no meta-commentary, no preamble,
  no explanation of your choices.
- Match the brand voice guide's tone exactly.
- Keep the copy concise and appropriate to a short marketing message
  (SMS/email/social length, not a full article).
"""
