"""Campaign copy generation — the second agent capability alongside insights
Q&A. Unlike answer_question()'s open-ended multi-round tool-calling loop,
this is a single retrieve-then-generate turn: fetch the restaurant's brand
voice guide, retrieve 1-2 similar past campaigns as few-shot grounding, then
one model call always on the Pro-tier model. See
docs/plans/phase-5-campaign-generation.md §5.3.
"""

import asyncio
import uuid
from dataclasses import dataclass, field

import structlog

from app.agent.llm_client import PRO_MODEL, FinalAnswer, GeminiClient, UserText
from app.agent.prompts.campaign_system_instruction import build_campaign_system_instruction
from app.agent.tools.restaurant_lookup import get_brand_voice_guide
from app.agent.tools.vector_search import SimilarCampaign, search_similar_campaigns

logger = structlog.get_logger()

CAMPAIGN_EXAMPLE_TOP_K = 2


@dataclass(frozen=True)
class CampaignGenerationResult:
    copy_text: str
    brand_voice_guide: str
    examples_used: list[SimilarCampaign] = field(default_factory=list)
    model: str = PRO_MODEL


async def generate_campaign(restaurant_id: uuid.UUID, brief: str) -> CampaignGenerationResult:
    structlog.contextvars.bind_contextvars(
        turn_id=str(uuid.uuid4()), restaurant_id=str(restaurant_id)
    )
    try:
        logger.info("campaign_turn_started", brief=brief, restaurant_id=str(restaurant_id))

        # Independent I/O — a DB lookup and an embedding call + DB lookup —
        # with no data dependency between them, so they run concurrently
        # rather than serializing two separate round-trips.
        brand_voice_guide, search_result = await asyncio.gather(
            get_brand_voice_guide(restaurant_id),
            search_similar_campaigns(
                restaurant_id, reference_text=brief, top_k=CAMPAIGN_EXAMPLE_TOP_K
            ),
        )
        examples = search_result.matches
        logger.info(
            "campaign_examples_retrieved",
            example_count=len(examples),
            example_ids=[str(e.campaign_id) for e in examples],
        )

        system_instruction = build_campaign_system_instruction(brand_voice_guide, examples)
        client = GeminiClient()
        turn_output = await client.generate_turn(
            history=[UserText(brief)],
            tools=[],
            system_instruction=system_instruction,
            model=PRO_MODEL,
        )
        if not isinstance(turn_output, FinalAnswer):
            # No tools were offered, so the model should never request one.
            # This isn't insights.py's round-cap case (an expected, budgeted
            # "ran out of rounds" outcome) — it's an SDK/model contract
            # violation with no rounds to exhaust, so it's deliberately left
            # to the generic unhandled_exception_handler (500) rather than
            # reusing AgentIncompleteError's "try rephrasing" messaging,
            # which doesn't describe this failure.
            raise RuntimeError(
                f"generate_turn() returned tool calls despite tools=[]: {turn_output!r}"
            )

        logger.info(
            "campaign_turn_completed", copy_text=turn_output.text, example_count=len(examples)
        )
        return CampaignGenerationResult(
            copy_text=turn_output.text,
            brand_voice_guide=brand_voice_guide,
            examples_used=examples,
            model=PRO_MODEL,
        )
    finally:
        structlog.contextvars.clear_contextvars()
