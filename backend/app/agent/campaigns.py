"""Campaign copy generation — the second agent capability alongside insights
Q&A. Agentic, like answer_question(): the model is offered the same
INSIGHTS_TOOLS roster and decides for itself whether a brief needs grounding
in real data before it can write specific copy (see
docs/decisions/016-agentic-campaign-generation.md). Brand voice and past-
campaign retrieval stay a fixed pre-fetch, not a tool call — that's about
tone, not a fact the model needs to decide whether to look up.
"""

import asyncio
import uuid
from dataclasses import dataclass, field

import structlog

from app.agent.exceptions import AgentIncompleteError
from app.agent.insights import (
    MAX_TOOL_CALL_ROUNDS,
    ToolCallRecord,
    _check_grounding,
    _resolve_tool_call_round,
)
from app.agent.llm_client import PRO_MODEL, ConversationEntry, FinalAnswer, GeminiClient, UserText
from app.agent.prompts.campaign_system_instruction import build_campaign_system_instruction
from app.agent.tool_registry import INSIGHTS_TOOLS
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
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


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

        system_instruction = build_campaign_system_instruction(
            restaurant_id, brand_voice_guide, examples
        )
        client = GeminiClient()
        history: list[ConversationEntry] = [UserText(brief)]
        tool_calls: list[ToolCallRecord] = []

        for _round_index in range(MAX_TOOL_CALL_ROUNDS):
            turn_output = await client.generate_turn(
                history=history,
                tools=INSIGHTS_TOOLS,
                system_instruction=system_instruction,
                model=PRO_MODEL,
            )

            if isinstance(turn_output, FinalAnswer):
                if not _check_grounding(turn_output.text, tool_calls):
                    logger.warning(
                        "possible_ungrounded_numeric_answer", answer=turn_output.text
                    )
                logger.info(
                    "campaign_turn_completed",
                    copy_text=turn_output.text,
                    example_count=len(examples),
                    tool_call_count=len(tool_calls),
                )
                return CampaignGenerationResult(
                    copy_text=turn_output.text,
                    brand_voice_guide=brand_voice_guide,
                    examples_used=examples,
                    model=PRO_MODEL,
                    tool_calls=tool_calls,
                )

            await _resolve_tool_call_round(turn_output, history, tool_calls)

        raise AgentIncompleteError(
            f"Campaign generation did not complete within {MAX_TOOL_CALL_ROUNDS} rounds."
        )
    finally:
        structlog.contextvars.clear_contextvars()
