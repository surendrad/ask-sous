# Phase 5: Campaign Generation — Implementation Plan

**Date:** 2026-07-16
**Status:** Complete
**Source:** implementation-plan.md Phase 5

---

## Goal

Add a second agent capability — grounded marketing campaign copy generation — alongside the existing insights Q&A path, and introduce explicit model routing so the project's fast/cheap-default-escalate-when-it-matters story is real, not just described. Campaign generation always routes to the Gemini Pro-tier model and grounds its output in two retrieved sources: the restaurant's own `brand_voice_guide` (Phase 1 schema field, unused until now) and 1–2 past campaigns retrieved via Phase 4's `search_similar_campaigns` (built in Phase 4, deliberately left unregistered as an LLM tool since it's used here as direct few-shot retrieval, not model-invoked). Insights Q&A keeps its existing Flash-2.5 default but gains an escalation heuristic: a turn that needs 3+ tool-call rounds, or whose question text signals an explicit request for deeper analysis, continues on the Pro-tier model instead of Flash.

Same live-credentials caveat as Phases 3 and 4: everything is built and tested against fixture/mocked Vertex AI responses. Actually generating campaign copy against the real Gemini Pro model requires the GCP setup in `docs/reference/gcp-setup.md`, which remains a manual, user-run prerequisite.

## Prerequisites

- Phases 3 and 4 complete: `GeminiClient`/`llm_client.py`, `tool_registry.py`, `answer_question()`, `/chat`, `EmbeddingClient`, `vector_search.search_similar_campaigns` (built but unregistered) all in place and passing.
- `Restaurant.brand_voice_guide` (Phase 1 schema) populated by seed data for all 5 restaurants — confirm via `seed-patterns.md` / direct query before writing tests.
- `campaigns.embedding` populated for at least some rows (Phase 4's `embed_seed_data.py` — hand-crafted vectors in tests, real population gated on live credentials same as Phase 4).
- Local Postgres running, migrated, seeded. Backend venv active.
- No new runtime dependencies.

## Implementation Details

### 5.1 Model routing (insights loop)

Add `PRO_MODEL = "gemini-2.5-pro"` to `app/agent/llm_client.py` alongside the existing `FLASH_MODEL`, following the same "confirm against what's actually available, don't assume the interview-prep-era name" caution as ADR-007 for Flash — record as part of ADR-010 (routing).

Add a pure routing function to `app/agent/insights.py` (or a small new `app/agent/routing.py` if it turns out to need its own tests file, kept alongside the loop otherwise — no need to over-split for a ~10-line function):

```python
_DEEPER_ANALYSIS_KEYWORDS = ("deep dive", "deeper analysis", "thorough", "in depth", "in-depth")
ESCALATION_TOOL_CALL_THRESHOLD = 3  # rounds already completed without a final answer

def _select_model(question: str, completed_tool_call_rounds: int) -> str:
    if completed_tool_call_rounds >= ESCALATION_TOOL_CALL_THRESHOLD:
        return PRO_MODEL
    if any(kw in question.lower() for kw in _DEEPER_ANALYSIS_KEYWORDS):
        return PRO_MODEL
    return FLASH_MODEL
```

Wire into `answer_question()`'s loop: compute the model at the top of each round (it can change mid-turn once the round threshold is crossed), pass it to `client.generate_turn(..., model=selected_model)`, and log `agent_turn_model_selected` with both the model and a `routing_reason` field (`"default"` / `"tool_call_threshold"` / `"keyword"`) instead of the current hardcoded `model=FLASH_MODEL` log call. `AgentTurnResult.model` becomes whatever model actually produced the final answer (already the right field — just needs to reflect the real selected model per round instead of the constant).

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests for `_select_model`: plain default returns Flash; `completed_tool_call_rounds=3` returns Pro; a question containing "deep dive" returns Pro even at round 0; case-insensitive keyword match
- [ ] Implement `_select_model`
- [ ] Write a failing unit test on `answer_question()` (mocked `GeminiClient`) asserting a 3-round tool-calling turn's final `generate_turn` call used `PRO_MODEL`, and that `AgentTurnResult.model == PRO_MODEL`
- [ ] Update `answer_question()`'s loop to call `_select_model` each round and pass the result through
- [ ] Update the `agent_turn_model_selected` log call to include `routing_reason`
- [ ] Write a failing unit test asserting the keyword path escalates a single-round turn (no tool calls needed) to Pro
- [ ] Confirm existing Phase 3 tests (which assume `FLASH_MODEL` throughout) still pass unmodified where they exercise the default path — update any that hardcoded model assumptions incompatible with the new signature

### 5.2 Brand voice + few-shot retrieval helper

Add `get_brand_voice_guide(restaurant_id: uuid.UUID) -> str` to a new small module `app/agent/tools/restaurant_lookup.py` (mirrors the existing `app/agent/tools/*.py` pure/impure split — a single parameterised `SELECT brand_voice_guide FROM restaurants WHERE id = :restaurant_id`, via `readonly_connection()`, raising a `ValueError` if no row is found, since this path is only reached after `/campaigns` has already confirmed the restaurant exists — same pattern `chat.py` uses).

### 5.3 Campaign generation orchestration

New module `app/agent/campaigns.py`, deliberately **not** a tool-calling loop like `insights.py` — campaign generation is a single retrieve-then-generate turn, not an open-ended multi-round investigation, so `MAX_TOOL_CALL_ROUNDS` and the tool dispatch loop don't apply here.

```python
@dataclass(frozen=True)
class CampaignExample:
    campaign_id: uuid.UUID
    copy_text: str

@dataclass(frozen=True)
class CampaignGenerationResult:
    copy_text: str
    brand_voice_guide: str
    examples_used: list[CampaignExample]
    model: str = PRO_MODEL

async def generate_campaign(restaurant_id: uuid.UUID, brief: str) -> CampaignGenerationResult:
    ...
```

Flow: bind `turn_id`/`restaurant_id` contextvars (same as `answer_question`) → fetch `brand_voice_guide` → call `search_similar_campaigns(restaurant_id, reference_text=brief, top_k=2)` → build the system instruction via `build_campaign_system_instruction(brand_voice_guide, examples)` → call `client.generate_turn(history=[UserText(brief)], tools=[], system_instruction=..., model=PRO_MODEL)`, expecting a `FinalAnswer` directly (no tool-calling round needed — `generate_turn` already returns `FinalAnswer` whenever the model doesn't request a tool call, so an empty `tools` list is sufficient, no new return-type handling required in `llm_client.py`). Log `campaign_turn_started`, `campaign_examples_retrieved` (with example count and IDs — the audit trail equivalent of `tool_call_result` for this path), `campaign_turn_model_selected` (`model=PRO_MODEL`, always — no routing decision to log here since it's a fixed heuristic per implementation-plan.md 5.2), and `campaign_turn_completed`.

If `search_similar_campaigns` returns zero matches (e.g. a restaurant with no embedded past campaigns yet), proceed anyway with brand voice alone — do not treat this as an error, per the same "if it returns no matches, say so honestly" spirit as the insights review-search rule, but for generation the honest behavior is simply generating from brand voice alone and noting in the system instruction that no past examples were available, rather than refusing.

### 5.4 Campaign system instruction

New `app/agent/prompts/campaign_system_instruction.py`, mirroring `insights_system_instruction.py`'s `build_*` pattern:

```python
def build_campaign_system_instruction(brand_voice_guide: str, examples: list[CampaignExample]) -> str:
    ...
```

Template covers: role framing ("You are Ask Sous, writing a marketing campaign for a restaurant"), the brand voice guide verbatim, the retrieved past campaign examples formatted as few-shot text (or an explicit "no past campaign examples are available for this restaurant" note when the list is empty), and output rules (write only the campaign copy itself, match the brand voice, keep it channel-appropriate length, no meta-commentary).

**Tasks (red-green-refactor) for 5.2–5.4:**
- [ ] Write a failing unit test for `get_brand_voice_guide` (fixture DB) — returns the correct string; raises `ValueError` for an unknown restaurant_id
- [ ] Implement `get_brand_voice_guide`
- [ ] Write a failing unit test for `build_campaign_system_instruction` — brand voice and both examples appear in the output; empty-examples case produces the "no past examples" note instead of an empty section
- [ ] Implement `build_campaign_system_instruction`
- [ ] Write a failing unit test for `generate_campaign` (mocked `GeminiClient`, mocked `search_similar_campaigns`, mocked `get_brand_voice_guide`) asserting: `PRO_MODEL` is always used; retrieved examples are passed into the system instruction; the returned `CampaignGenerationResult.copy_text` matches the mocked `FinalAnswer.text`
- [ ] Implement `generate_campaign`
- [ ] Write a failing unit test asserting `generate_campaign` proceeds (not an error) when `search_similar_campaigns` returns zero matches
- [ ] Write a failing unit test asserting audit log events (`campaign_turn_started`, `campaign_examples_retrieved`, `campaign_turn_completed`) are emitted with expected fields (structlog `capsys`/caplog pattern, matching `test_insights_logging.py`)

### 5.5 `/campaigns` API endpoint

New `app/api/campaigns.py`, mirroring `chat.py`'s shape exactly (restaurant-exists check via `readonly_connection()`, same `error_response`/`success` envelope):

```python
class CampaignRequest(BaseModel):
    restaurant_id: uuid.UUID
    brief: str = Field(min_length=1, max_length=2000)

class CampaignExampleSummary(BaseModel):
    campaign_id: uuid.UUID
    copy_text: str

class CampaignResponseData(BaseModel):
    copy_text: str
    examples_used: list[CampaignExampleSummary]
    model: str

@router.post("/campaigns")
async def generate_campaign_endpoint(payload: CampaignRequest) -> dict: ...
```

Register the router in `app/main.py` alongside `chat.router`. Reuses the existing `AgentUnavailableError`/`AgentIncompleteError` exception handlers unchanged — `generate_campaign` raises the same `AgentUnavailableError` on any Vertex AI failure via the shared `GeminiClient`, no new exception class needed. (`AgentIncompleteError` doesn't apply to this path since there's no round cap to exceed, but the handler stays registered globally regardless.)

**Tasks (red-green-refactor):**
- [ ] Write a failing integration test (`test_campaigns_endpoint.py`, mirroring `test_chat_endpoint.py`) — 404 for unknown restaurant; success shape for a known restaurant with mocked `generate_campaign`
- [ ] Implement the endpoint
- [ ] Write a failing end-to-end integration test (mirroring `test_chat_end_to_end.py`/`test_chat_review_search_end_to_end.py`) exercising the full retrieve-then-generate flow against fixture data with hand-crafted campaign embeddings in the seeded test DB
- [ ] Implement/wire whatever the end-to-end test reveals is still missing

## Testing

### Integration Tests
- [ ] `/campaigns` 404s for an unknown restaurant, same as `/chat`
- [ ] `/campaigns` end-to-end: brief in, grounded copy out, `examples_used` reflects real retrieved rows from the seeded DB
- [ ] Insights routing: a manually-constructed 3-tool-call-round fixture conversation ends up on `PRO_MODEL`

### Manual Verification
- [ ] Confirm `Restaurant.brand_voice_guide` is populated and distinct per restaurant in the seed data (spot-check via direct query)
- [ ] Trace one campaign generation call's log lines end-to-end and confirm no naked/invented content beyond the retrieved brand voice + examples

## User Acceptance Tests

- [ ] UAT-5.1: Owner requests a campaign and receives copy grounded in their brand voice
- [ ] UAT-5.2: Campaign copy reflects retrieved past-campaign style when similar past campaigns exist
- [ ] UAT-5.3: Campaign generation for a restaurant with no past campaign examples still succeeds, generating from brand voice alone
- [ ] UAT-5.4: A simple insights question still routes to Flash (spot-check logged model)
- [ ] UAT-5.5: A complex, multi-tool-call insights question escalates to Pro mid-turn (spot-check logged model + routing_reason) — **requires live credentials**
- [ ] UAT-5.6: An explicit "give me a deep dive on X" question routes straight to Pro — **requires live credentials**

## Documentation Updates

- [ ] ADR-010: model routing heuristic (thresholds, keyword list, why Pro is fixed for campaigns rather than routed)
- [ ] Update `docs/tasks.md` with Phase 5 tasks
- [ ] Update `docs/uat.md` with UAT-5.1–5.6
- [ ] Update `docs/changelog.md` with Phase 5 completion
- [ ] Update `CLAUDE.md`: new `/campaigns` endpoint, new tool-adjacent modules, routing heuristic summary
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 5 status

## Security Considerations

No new security-relevant surface: `/campaigns` follows the exact same restaurant-scoping and read-only DB boundary as `/chat`. No new write paths — campaign generation reads `brand_voice_guide` and past campaigns but does not persist generated copy to the `campaigns` table in this phase (that's a "save/send campaign" feature, not in scope per master-plan.md — copy is returned to the caller only).

## Dependencies & Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| `gemini-2.5-pro` model ID has moved on since interview-prep-era naming | Medium | Medium | Same as ADR-007's Flash caution — confirm against the installed SDK/live model catalogue before UAT-5.5/5.6 |
| Routing thresholds (3 rounds, keyword list) feel arbitrary without real usage data | Low | Medium | Documented as an explicit, adjustable heuristic in ADR-010, not hardcoded silently |
| No live credentials to verify actual Pro-tier output quality/tone-matching | Medium | High (same gap as Phases 3–4) | Fixture-based tests verify orchestration correctness; UAT-5.1–5.3 completable without credentials since they only require correctness of retrieval + wiring — actual generation quality assessment is deferred with UAT-5.5/5.6 |
