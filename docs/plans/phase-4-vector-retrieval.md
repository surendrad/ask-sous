# Phase 4: Vector Retrieval — Implementation Plan

**Date:** 2026-07-15
**Status:** In Progress
**Source:** implementation-plan.md Phase 4

---

## Goal

Turn Phase 1's two nullable `vector(768)` columns (`reviews.embedding`, `campaigns.embedding` — schema-only since ADR-003, unpopulated since seeding) into actual searchable qualitative context: a Vertex AI embedding adapter mirroring Phase 3's `GeminiClient` pattern, a follow-up script that populates both columns deterministically from the fixed seed data, and a pgvector similarity-search capability wired into the agent's toolset the same way Phase 3 wired in its four aggregation tools plus the raw SQL tool. This is the phase where "why was revenue down" (numbers) gets a companion capability — "what are customers actually saying" (qualitative grounding) — and where the retrieval mechanism Phase 5 needs for campaign few-shot examples gets built once, generically, rather than being bolted on ad hoc when campaign generation needs it.

Like Phase 3, this phase inherits the no-live-GCP-credentials constraint (`.env` still has placeholder `GOOGLE_APPLICATION_CREDENTIALS`/`GCP_PROJECT_ID` values; `docs/reference/gcp-setup.md`'s checklist hasn't been run). Everything is designed to be buildable and testable today via the same adapter-boundary strategy Phase 3 established (ADR-007) — mock at the SDK call boundary, test everything above it with plain dataclasses/`AsyncMock`. The one piece of this phase that genuinely cannot be exercised without live credentials is the actual population of `reviews.embedding`/`campaigns.embedding` for the real seeded data (an outbound network call per text, times 154 rows) — that gap is tracked explicitly in Dependencies & Risks and split into gated UAT items, exactly like Phase 3's UAT-3.5/3.6.

## Prerequisites

- Phases 1 and 3 complete (per implementation-plan.md's dependency table: Phase 4 depends on 1, 3): full seeded schema with `vector(768)` columns present but `NULL` on all 138 reviews / 16 campaigns (`docs/reference/seed-patterns.md`); `GeminiClient`/`llm_client.py` adapter pattern, `tool_registry.py`'s `INSIGHTS_TOOLS`/`TOOL_DISPATCH` pairing, `answer_question()`'s orchestration loop, and `/chat` all in place and passing their full test suites.
- Local Postgres instance running, migrated, seeded (`cd backend && alembic upgrade head && python -m app.seed.seed`) — same "whatever `DATABASE_URL` points at" framing as every prior phase, Docker not installed in this environment.
- Backend virtualenv active, `pip install -e ".[dev]"` from `backend/`.
- **No new runtime dependencies this phase.** `google-genai` (already added in Phase 3) covers both Gemini chat calls and Vertex AI embedding calls through the same SDK/client — no new package needed. `pgvector` (already added in Phase 1 for the SQLAlchemy column type) is also already present.
- **GCP/Vertex AI setup is NOT a prerequisite for building or testing this phase**, with one explicit exception: actually running `python -m app.seed.embed_seed_data` against the real seeded database requires live credentials, because it makes real outbound embedding calls. Everything else — the `EmbeddingClient` adapter, the population script's own logic, the retrieval tool, its registration in `tool_registry.py`, and all automated tests — is buildable and verifiable against fixtures/mocks today, mirroring Phase 3's ADR-007 split exactly.

## Implementation Details

### 4.1 `EmbeddingClient` — a second, narrowly-scoped Vertex AI adapter

**Same pattern as `GeminiClient`, deliberately, not a new pattern invented for this phase.** `backend/app/agent/embedding_client.py` wraps `google.genai.Client` behind a small `EmbeddingClient` class that accepts and returns only plain Python types (`list[str]` in, `list[list[float]]` out) — never a raw `google.genai.types` object crosses out of this module. This extends (not replaces) the "only module permitted to import `google.genai`" rule from ADR-007/CLAUDE.md: after this phase, **two** modules in `app/agent/` are permitted to import `google.genai` directly — `llm_client.py` (chat/function-calling) and `embedding_client.py` (embeddings) — kept as two separate files rather than merged into one, since they wrap two different Vertex AI capabilities with different call shapes, different failure semantics worth distinguishing in logs (`gemini_call_failed` vs `embedding_call_failed`), and no shared state; merging them would just make one file responsible for two unrelated SDK surfaces. `grep -rn "from google" backend/app/agent/ backend/app/api/` should show hits in exactly these two files after this phase, never a third.

**Confirm the exact embedding model.** ADR-003 sized both vector columns at `vector(768)` on the assumption of `text-embedding-004` (768-dimensional native output) as the most likely Vertex AI embedding model, while explicitly leaving the door open for `gemini-embedding-001` (whose native output is larger, but which supports an `output_dimensionality` parameter to truncate to 768). This phase makes that call for real: record the confirmed model ID as `EMBEDDING_MODEL` in `embedding_client.py`, and — since neither model choice can actually be *verified* against a live model catalogue in this environment — write the decision down as ADR-008 with the same "not yet verified against a live listing, confirm before the live-credentials UAT items" honesty ADR-007 used for the Flash model ID. Default to `text-embedding-004` (matching ADR-003's own stated assumption, so no follow-up column migration is needed) unless something concrete surfaces during implementation to prefer the other.

```python
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSIONS = 768  # must match ADR-003's vector(768) columns exactly

class EmbeddingClient:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._client = genai.Client(
            vertexai=True, project=settings.gcp_project_id, location=settings.gcp_region
        )

    async def embed_texts(
        self, texts: list[str], *, model: str = EMBEDDING_MODEL
    ) -> list[list[float]]:
        """Returns one EMBEDDING_DIMENSIONS-length vector per input text, in
        the same order as `texts`. Raises AgentUnavailableError (reusing the
        exact exception Phase 3 introduced — no new exception class needed;
        this is the same "Vertex AI call failed" failure mode, just a
        different SDK surface) on any SDK-level failure."""
```

Internally: call the SDK's embedding endpoint (confirm the exact method name against the installed `google-genai` version during implementation — `client.models.embed_content(model=..., contents=texts, config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS))` is the expected shape at time of writing, following the same "confirm against the installed package, don't assume the interview-prep-era name is still exact" caution ADR-007 already applied to the Flash model ID) via `asyncio.to_thread(...)` (matching `GeminiClient.generate_turn`'s own thread-offload pattern, since the SDK client is synchronous under the hood). Catch `errors.APIError`/`errors.ClientError`/`errors.ServerError` exactly as `GeminiClient` does, log via `structlog.error("embedding_call_failed", exc_info=exc)`, and re-raise as `AgentUnavailableError` — reused directly from `app/agent/exceptions.py`, not duplicated, since this is the identical "the agent is temporarily unavailable" failure mode from the caller's point of view, just triggered by a different Vertex AI call.

**A pure dimension guard, `_validate_dimensions(vectors: list[list[float]], expected: int = EMBEDDING_DIMENSIONS) -> None`:** raises `ValueError` if any returned vector's length doesn't match `EMBEDDING_DIMENSIONS`. This exists because a dimension mismatch would otherwise surface only as an opaque Postgres error at `INSERT`/`UPDATE` time (the `vector(768)` column rejects any other length) — catching it in Python first gives a clear, attributable error message instead. Called at the end of `embed_texts()` before returning.

**Tasks (red-green-refactor):**
- [ ] Write a failing unit test (`backend/tests/unit/test_embedding_client.py`) asserting `EmbeddingClient()` constructs its underlying `genai.Client` with `vertexai=True` and `project`/`location` from a monkeypatched `Settings` — no network call, mirrors `test_llm_client.py`'s equivalent test exactly
- [ ] Implement `EmbeddingClient.__init__` to make it pass
- [ ] Write a failing unit test asserting `EmbeddingClient.embed_texts(["a", "b"])` correctly translates a **hand-built, real SDK embedding response object** (constructed directly, no network call) containing two embeddings into `list[list[float]]` of length 2, each inner list length `EMBEDDING_DIMENSIONS`, in the same order as the input texts
- [ ] Implement the translation logic in `embed_texts()` to make this pass (SDK call mocked via `unittest.mock.patch.object` at the call boundary, mirroring `test_llm_client.py`'s pattern for `generate_content`)
- [ ] Write a failing unit test asserting `embed_texts()` translates a mocked SDK-raised `errors.APIError` into `AgentUnavailableError` with the original exception accessible via `.__cause__` — mirrors `test_agent_exceptions.py`'s equivalent `GeminiClient` test
- [ ] Implement the catch/translate/re-raise to make this pass
- [ ] Write failing unit tests for `_validate_dimensions()`: a list of correctly-sized vectors passes without raising; a list containing one vector of the wrong length raises `ValueError` naming which index was wrong
- [ ] Implement `_validate_dimensions()`, wire it into `embed_texts()`, to make these pass
- [ ] Write a failing unit test asserting `embed_texts()` is deterministic at the plumbing level: given a mocked SDK call that returns the *same* fixed response object for the *same* input text across two separate calls, `embed_texts()` returns byte-identical output both times (this is the automated, mock-level half of implementation-plan.md's "deterministic output for identical input" requirement — true model-level determinism against a live embedding model is a separate, live-credentials-gated verification, tracked in Dependencies & Risks and UAT-4.4)
- [ ] Confirm this passes with the existing implementation (no new code expected — this test documents and locks in a property the translation logic already has by construction, since it does no randomness/timestamping of its own)
- [ ] Refactor: confirm `grep -rn "from google" backend/app/agent/ backend/app/api/` shows hits in exactly `llm_client.py` and `embedding_client.py`, nowhere else

### 4.2 Seed-time embedding population script

**`backend/app/seed/embed_seed_data.py`** — a follow-up to `seed.py`, not a merge into it. Kept separate because `seed.py`'s job (deterministic Faker-driven row generation, fully offline, no external dependency) and this script's job (a network call to Vertex AI per batch of texts) have genuinely different failure modes and retry/idempotency concerns — collapsing them would mean `python -m app.seed.seed` starts requiring live GCP credentials to complete at all, breaking every earlier phase's "seed the database" story for anyone without credentials yet. Run via `python -m app.seed.embed_seed_data`, uses the same privileged DB session `seed.py` already uses (`app.db.session.async_session_maker`, **not** `readonly_connection()` — this is a data-population script that needs `UPDATE` access, exactly the same reasoning `seed.py` itself already establishes for using admin credentials rather than the read-only role).

**Pure/impure split, per CLAUDE.md's established convention:**
- Pure: `_chunk(items: Sequence[T], size: int) -> Iterator[list[T]]` — batches texts for the embedding call (Vertex AI embedding endpoints typically cap the number of texts per request; even though this project's actual volume — 138 reviews + 16 campaigns = 154 texts total — comfortably fits in one or two batches at any plausible limit, chunking is implemented properly rather than assumed away, since it costs little and avoids a silent failure if a future larger seed dataset is ever generated).
- Pure: `_build_update_payloads(ids: Sequence[uuid.UUID], vectors: Sequence[list[float]]) -> list[dict]` — zips row IDs with their corresponding vectors into the `[{"id": ..., "embedding": ...}, ...]` shape SQLAlchemy Core's bulk `update()` expects. Tested with zero DB/network involvement.
- Impure: `async def embed_and_store_reviews(session, embedding_client) -> int` and `async def embed_and_store_campaigns(session, embedding_client) -> int` — each: `SELECT id, review_text FROM reviews` (or `id, copy_text FROM campaigns`) via the privileged session, batch through `_chunk`, call `embedding_client.embed_texts()` per batch, build payloads via `_build_update_payloads`, bulk `UPDATE` via `session.execute(update(Review.__table__), payloads)`, return the row count updated. **Idempotent by design** — always re-fetches and re-embeds every row regardless of whether `embedding` is already populated (simpler and more honest than a "only fill in `NULL`s" partial-update mode, and matches `seed.py`'s own "truncate and regenerate cleanly" idempotency philosophy; re-running always produces the same result given the same input text and a deterministic embedding model).
- `main()`: opens one session, runs both `embed_and_store_*` functions, prints a summary (`reviews embedded: 138`, `campaigns embedded: 16`) — mirrors `seed.py -> main()`'s own print-summary convention exactly.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_embed_seed_data.py`) for `_chunk()`: a list shorter than `size` yields one chunk containing everything; a list exactly divisible by `size` yields the expected number of equal chunks; a list with a remainder yields a final, shorter chunk; `size` of the full 154-row scale with a realistic batch size (e.g. 100) yields exactly 2 chunks
- [ ] Implement `_chunk()` to make these pass
- [ ] Write failing unit tests for `_build_update_payloads()`: given 3 ids and 3 vectors, returns 3 dicts each with the correct `id`/`embedding` pairing, order-preserving; a length mismatch between `ids` and `vectors` raises `ValueError` rather than silently zipping to the shorter length (guards against a batching bug pairing the wrong text with the wrong vector)
- [ ] Implement `_build_update_payloads()` to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_embed_seed_data_integration.py`) asserting `embed_and_store_reviews()`, run against the real seeded database with `EmbeddingClient` mocked (`AsyncMock` on `embed_texts`, returning a fixed, distinct 768-length vector per input batch — no network call), updates every one of the 138 seeded reviews' `embedding` column to a non-`NULL`, length-768 value, and returns `138`
- [ ] Implement `embed_and_store_reviews()` to make this pass
- [ ] Write the equivalent failing integration test for `embed_and_store_campaigns()` against the 16 seeded campaigns, asserting `16` rows updated
- [ ] Implement `embed_and_store_campaigns()` to make this pass
- [ ] Write a failing integration test asserting idempotency: running `embed_and_store_reviews()` twice in a row (same mocked `EmbeddingClient` behaviour both times) leaves every review's `embedding` value identical after the second run to after the first (byte-for-byte list equality) — proves re-running the script is safe and reproducible, matching `seed.py`'s own re-run guarantee
- [ ] Confirm this passes with the existing implementation (idempotency should already hold by construction — no partial-update branching exists to introduce drift)
- [ ] Refactor: confirm `embed_seed_data.py` never imports `app.agent.tools.db` (the read-only path) — it exclusively uses `app.db.session`'s privileged path, exactly like `seed.py`; add an explicit test asserting `readonly_connection` is never called during either `embed_and_store_*` function (monkeypatch it to a stub that fails the test if invoked, mirroring Phase 3's own pattern for proving "validation happens before any DB call")

### 4.3 Vector similarity search — the retrieval tool

**`backend/app/agent/tools/vector_search.py`**, following the exact pure/impure split every tool module in `app/agent/tools/` already uses.

**Pure helpers:**
- `_format_vector_literal(vector: Sequence[float]) -> str` — renders a Python `list[float]` as the pgvector text literal format (`"[0.123,0.456,...]"`), used to bind the query vector into a parameterised `text()` query via an explicit `CAST(:query_vector AS vector)`, rather than relying on a registered asyncpg-level vector type codec. Chosen deliberately over driver-level codec registration (`pgvector.asyncpg.register_vector`) because it needs no per-connection setup hook in `readonly_connection()` (which deliberately stays minimal and connection-pool-free per ADR-005) and keeps the vector-binding logic visible and independently unit-testable as a plain string-formatting function, at the cost of one explicit `CAST` in the SQL text — a small, worthwhile tradeoff for a 154-row-scale project. Record this choice, and the "no ANN index needed at this scale" decision below, in ADR-009.
- `_clamp_top_k(top_k: int | None, *, default: int, max_value: int) -> int` — mirrors the raw SQL tool's row-cap philosophy (Phase 3, `_enforce_row_cap`): a model-supplied `top_k` is clamped to `[1, max_value]`, `None` falls back to `default`. Defends against a runaway request (e.g. a model asking for `top_k=100000`) the same way the raw SQL tool defends against an unbounded query — cheap, and consistent with the project's existing defense-in-depth posture for anything LLM-influenced.

**Impure functions:**

```python
@dataclass(frozen=True)
class SimilarReview:
    review_id: uuid.UUID
    rating: int
    review_text: str
    source: str
    distance: float  # cosine distance, 0.0 = identical, larger = less similar

@dataclass(frozen=True)
class ReviewSearchResult:
    restaurant_id: uuid.UUID
    query: str
    matches: list[SimilarReview]

async def search_reviews(
    restaurant_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> ReviewSearchResult: ...

@dataclass(frozen=True)
class SimilarCampaign:
    campaign_id: uuid.UUID
    name: str
    channel: str
    copy_text: str
    distance: float

@dataclass(frozen=True)
class CampaignSearchResult:
    restaurant_id: uuid.UUID
    reference_text: str
    matches: list[SimilarCampaign]

async def search_similar_campaigns(
    restaurant_id: uuid.UUID,
    reference_text: str,
    top_k: int | None = None,
    embedding_client: EmbeddingClient | None = None,
) -> CampaignSearchResult: ...
```

Both: embed the query/reference text via `(embedding_client or EmbeddingClient()).embed_texts([text])`, then run a parameterised nearest-neighbour query via `readonly_connection()` — the exact same read-only boundary every other tool uses, nothing new introduced:

```sql
SELECT id, rating, review_text, source,
       embedding <=> CAST(:query_vector AS vector) AS distance
FROM reviews
WHERE restaurant_id = :restaurant_id AND embedding IS NOT NULL
ORDER BY distance
LIMIT :top_k
```

(`campaigns` variant selects `id, name, channel, copy_text` and orders/filters identically.) Cosine distance (`<=>`) is used rather than Euclidean (`<->`) — the standard choice for text-embedding similarity, where the *direction* of the embedding (semantic content) matters more than its magnitude. `embedding IS NOT NULL` is an explicit, deliberate filter, not an oversight — it's what makes `search_reviews`/`search_similar_campaigns` behave correctly and non-crashingly *before* 4.2's population script has ever been run (returning zero matches rather than erroring on rows with a `NULL` vector), which matters concretely for this implementation environment where the real seeded rows will, for now, have no embeddings at all.

**No ANN index (`ivfflat`/`hnsw`) is added this phase.** At 138 reviews / 16 campaigns, a full sequential scan with the `<=>` operator is exact and fast — an ANN index exists to trade exactness for speed at a scale (tens of thousands of rows and up) this project's seed data never approaches. Adding one now would be premature optimisation with a real cost (approximate, not exact, nearest-neighbour results) and no measurable benefit; documented as a deliberate scope decision in ADR-009, revisit only if the dataset size assumption ever changes (implementation-plan.md's own "Dataset size... revisit if needed" open item).

**Tool registration — reviews only, this phase.** `tool_registry.py` gains a sixth `ToolDeclaration`/`TOOL_DISPATCH` entry, `search_customer_reviews`, wired into `INSIGHTS_TOOLS` exactly like the existing five, so the model can call it for qualitative Q&A ("what are customers saying about slow service?"). `search_similar_campaigns`, by contrast, is **not** registered as an LLM-callable tool this phase — it's a plain importable async function, ready for Phase 5 to call directly as a deterministic pre-generation step when assembling campaign few-shot context (master-plan.md §4.3: "the agent retrieves the restaurant's brand voice guide and 1–2 past campaign examples... before generating copy" — a Python-orchestrated retrieval step, not something the model decides to invoke mid-conversation). This split — one function exposed as a model-callable tool, the other exposed only to application code — is a genuine design decision, not an oversight, and is recorded in ADR-009 alongside the distance-operator and no-index choices.

```python
ToolDeclaration(
    name="search_customer_reviews",
    description=(
        "Searches customer reviews for a restaurant by semantic similarity "
        "to a natural-language query. Use this for qualitative questions "
        "about what customers are saying (e.g. 'what do customers say about "
        "the service?'), not for numeric/aggregate questions."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "restaurant_id": _RESTAURANT_ID_PARAM,
            "query": {"type": "STRING", "description": "What to search reviews for, in plain language."},
            "top_k": {"type": "INTEGER", "description": "Optional: how many reviews to return (default 5, max 20)."},
        },
        "required": ["restaurant_id", "query"],
    },
)
```

`parse_args`: `restaurant_id` via the existing `_parse_uuid`, `query` passed through as-is, `top_k` parsed as `int` when present (reusing `get_item_velocity`'s existing optional-`top_n` handling as the direct precedent).

**System instruction update.** `app/agent/prompts/insights_system_instruction.py`'s `build_insights_system_instruction()` gains one additional sentence: guidance to use `search_customer_reviews` for qualitative "what are customers saying" questions, and — critically, matching the existing grounding rule's own phrasing style — an explicit instruction that review content quoted in an answer must come from this tool's results, never invented, exactly mirroring the existing "only state a number if it was returned by a tool call" rule but for qualitative claims about review content.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_vector_search.py`) for `_format_vector_literal()`: a 3-element vector formats as the exact string `"[0.1,0.2,0.3]"`; an empty vector formats as `"[]"`; formatting round-trips through `sqlglot`/is valid enough to be embedded directly in SQL text (assert no characters requiring escaping appear in the output for any float input)
- [ ] Implement `_format_vector_literal()` to make these pass
- [ ] Write failing unit tests for `_clamp_top_k()`: `None` returns `default`; a value within `[1, max_value]` passes through unchanged; a value above `max_value` clamps to `max_value`; a value of `0` or negative clamps to `1` (never zero-or-fewer results silently)
- [ ] Implement `_clamp_top_k()` to make these pass
- [ ] Write failing unit tests for `search_reviews()`/`search_similar_campaigns()` mocking both `EmbeddingClient.embed_texts` (`AsyncMock`, returns a fixed vector) and the DB fetch step (monkeypatch the module-level query-execution helper, mirroring how Phase 2/3 tools isolate DB calls in their own unit tests) — asserting: the embedding client is called with exactly `[query]`/`[reference_text]`; the returned `ReviewSearchResult`/`CampaignSearchResult` correctly maps fetched rows into `SimilarReview`/`SimilarCampaign` dataclasses; `top_k` is passed through `_clamp_top_k()` before being used as the query's `LIMIT` bind value
- [ ] Implement `search_reviews()`/`search_similar_campaigns()` (embed → clamp top_k → format vector literal → query via `readonly_connection()` → map rows) to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_vector_search_integration.py`) with an explicit setup/teardown fixture: before the test, `UPDATE` three known seeded review rows for one restaurant (fetched by `review_text` LIKE match or by taking the first three rows for that restaurant) to three hand-crafted, orthogonal-ish 768-dimension vectors (e.g. one with `[1.0, 0.0, 0.0, ...]`-style structure, one near-identical to it, one far away) via a direct privileged-session `UPDATE`; after the test, reset those rows' `embedding` back to `NULL` in a `finally`/fixture-teardown block, so the shared dev database is left exactly as `seed.py` last left it
- [ ] Implement the test body: with `EmbeddingClient` mocked to return the "near-identical" hand-crafted vector as the query embedding, assert `search_reviews()` returns the genuinely-identical row first (distance ≈ 0), the near-identical row second, and the far-away row last (or excluded if `top_k` is small) — proving the actual pgvector `<=>` operator, `ORDER BY`, and `LIMIT` work correctly against the real `vector(768)` column, independent of whether the vectors are "real" semantic embeddings
- [ ] Write a failing integration test asserting restaurant scoping: hand-craft embeddings for reviews belonging to two *different* seeded restaurants with the same near-identical vector, then assert `search_reviews(restaurant_id=<first>, ...)` never returns the second restaurant's review, even though it would have been the nearest match by distance alone — proving the `WHERE restaurant_id = :restaurant_id` clause is genuinely enforced, not merely present in the SQL text
- [ ] Implement/confirm the scoping clause makes this pass
- [ ] Write a failing integration test asserting `search_reviews()` against a restaurant with **no** populated embeddings (the default state for every restaurant in this environment, since 4.2's population script requires live credentials) returns an empty `matches` list, not an error — proving the `embedding IS NOT NULL` filter and empty-result path both work cleanly
- [ ] Confirm this passes with the existing implementation
- [ ] Write failing unit tests (extending `backend/tests/unit/test_tool_registry.py`) asserting `INSIGHTS_TOOLS` now has six declarations (update the existing "five" assertion), the new `search_customer_reviews` declaration has the expected parameter names/types, and `TOOL_DISPATCH["search_customer_reviews"]` is present and dispatches to `vector_search.search_reviews`
- [ ] Implement the registration in `tool_registry.py` to make these pass
- [ ] Write a failing unit test for `search_customer_reviews`'s `parse_args`: valid UUID/string/integer inputs parse correctly; a malformed `restaurant_id` raises `ValueError` (not an uncaught exception) — same shape as every other tool's `parse_args` test
- [ ] Implement `parse_args` to make this pass
- [ ] Write a failing unit test (`backend/tests/unit/test_insights_system_instruction.py`, extending the existing file) asserting `build_insights_system_instruction()`'s output mentions `search_customer_reviews` and includes qualitative-grounding guidance
- [ ] Implement the system instruction update to make this pass
- [ ] Refactor: confirm `vector_search.py` never imports `app.db.session` (the privileged path) — it exclusively uses `readonly_connection()`, exactly like every other `app/agent/tools/` module; confirm `search_similar_campaigns` is genuinely unreferenced by `tool_registry.py`/`INSIGHTS_TOOLS` this phase (grep for it — it should only appear in `vector_search.py` and its own tests, ready for Phase 5 to import directly)

## Testing

The red-green-refactor cycle is embedded in each sub-section's tasks above. This section covers cross-cutting verification. Testing depth for this phase is the project's default **Practical** bar (matching Phase 3, not Phase 1/2's stricter one) — this is retrieval/integration plumbing, not the data-correctness core metric.

### Integration Tests
- [ ] Full-suite pass: `cd backend && pytest` runs every unit/integration test from Phases 0–3 alongside this phase's new tests, no regressions
- [ ] End-to-end mocked flow: a single integration test driving `POST /chat` with a mocked `GeminiClient` (one round: a `search_customer_reviews` tool call, then a final answer quoting review content) against a test-scoped set of hand-crafted embedded reviews (same setup/teardown pattern as 4.3's integration tests) — proving the full stack (chat endpoint → orchestration loop → tool dispatch → real pgvector query → real logging → real envelope) composes correctly for the new tool, not just in isolation
- [ ] Confirm the existing grounding-guard test (`test_grounding_guard.py`) still passes unmodified — the new tool doesn't change the "digit in answer with zero tool calls" heuristic's behaviour, since review-search calls are still logged as ordinary tool calls

### Manual Verification
- [ ] `cd backend && ruff check . && ruff format --check .` — confirm no errors
- [ ] `cd backend && pytest` — confirm the full suite passes
- [ ] `grep -rn "from google" backend/app/agent/ backend/app/api/` — confirm SDK imports are confined to `llm_client.py` and `embedding_client.py`
- [ ] With `EmbeddingClient` mocked and a few reviews hand-embedded via a throwaway script, send a `POST /chat` request asking a qualitative question and visually inspect the JSON response's `tool_calls` entry for `search_customer_reviews`, confirming real review text and distances are present
- [ ] Confirm `python -m app.seed.embed_seed_data --help`-equivalent (i.e. just running it) fails fast and clearly with placeholder `.env` credentials (an `AgentUnavailableError`-driven message, not a silent hang or an unrelated stack trace) — proving the script fails the *right* way in this environment rather than papering over the gap

## User Acceptance Tests

UAT scenarios for this phase, to be added to `docs/uat.md`. Three scenarios are completable now against mocked/fixture data; two are explicitly marked as requiring live Vertex AI credentials, matching Phase 3's UAT-3.5/3.6 pattern.

- [ ] UAT-4.1: The agent answers a qualitative question using the review-search tool — With the backend running, `EmbeddingClient` mocked, and a small set of seeded reviews hand-embedded with known vectors (test fixture setup), send a request equivalent to "what are customers saying about the service?" and confirm the response's `tool_calls` array names `search_customer_reviews` with a real `query` argument and real review text/ratings in its result, and that the final answer's claims about review content are traceable to that result.
- [ ] UAT-4.2: Review search is scoped to the correct restaurant — With two restaurants' reviews hand-embedded such that a review belonging to a *different* restaurant would otherwise be the nearest match, confirm a request scoped to the first restaurant never surfaces the second restaurant's review in either `tool_calls` or the final answer.
- [ ] UAT-4.3: A qualitative question asked before embeddings exist returns an honest "no data" answer, not a crash or a hallucination — Before running `embed_seed_data.py` (the default state of this environment's database right now), ask a qualitative review question and confirm the tool call completes with zero matches and the agent's answer honestly states it has no review data to draw on, rather than inventing plausible-sounding review content.
- [ ] UAT-4.4 **(requires live Vertex AI credentials — complete `docs/reference/gcp-setup.md` first):** The embedding population script runs successfully against real data — With `.env` populated with real GCP values, run `python -m app.seed.embed_seed_data` and confirm it completes without error, reports `reviews embedded: 138` and `campaigns embedded: 16`, and a direct `psql` query (`SELECT COUNT(*) FROM reviews WHERE embedding IS NOT NULL;`) confirms all 138 rows (and all 16 campaigns) are populated. Re-run the script a second time and confirm it completes again with identical row counts (idempotency holds against the real model, not just the mocked test).
- [ ] UAT-4.5 **(requires live Vertex AI credentials):** A live qualitative search returns semantically relevant reviews — After UAT-4.4, ask a real natural-language qualitative question for one of the five seeded restaurants (e.g. "what do customers say about wait times at Golden Skillet?") and confirm the reviews returned by `search_customer_reviews` in the response's `tool_calls` are genuinely topically relevant (mention service speed, waiting, etc.) rather than semantically unrelated matches, and that the final answer's characterisation of customer sentiment is faithful to what those specific reviews say.

## Documentation Updates

- [ ] Update `docs/tasks.md` with Phase 4 tasks (following the exact status-emoji convention used for Phases 0–3)
- [ ] Update `docs/uat.md` with UAT-4.1 through UAT-4.5, clearly marking 4.4/4.5 as requiring live credentials, matching the UAT-3.5/3.6 formatting convention exactly
- [ ] Update `docs/changelog.md` with a Phase 4 completion summary, explicitly noting which parts were verified live vs. only against fixtures/hand-crafted vectors, and confirming no new runtime dependencies were needed
- [ ] Write `docs/decisions/008-embedding-model-and-client-adapter.md` (ADR) — the confirmed embedding model ID (`text-embedding-004`, per ADR-003's own assumption, or the reasoning if `gemini-embedding-001` was chosen instead), the decision to add a second, narrowly-scoped adapter (`embedding_client.py`) alongside `llm_client.py` rather than merging them, and an explicit note (mirroring ADR-007) that the exact SDK method name/shape for embedding calls should be confirmed against the installed `google-genai` version once live credentials exist
- [ ] Write `docs/decisions/009-vector-retrieval-tool-design.md` (ADR) — cosine distance (`<=>`) over Euclidean, the vector-literal-via-`CAST` binding approach over asyncpg-level codec registration, the decision not to add an ANN index at this data scale, and the split between `search_customer_reviews` (LLM-callable tool, registered this phase) and `search_similar_campaigns` (plain function, built this phase but wired into Phase 5's campaign generation, not the model's toolset)
- [ ] Update `CLAUDE.md`: add `app/agent/embedding_client.py` alongside `llm_client.py` in the "only modules permitted to import `google.genai`" bullet; note the sixth insights tool (`search_customer_reviews`) and the qualitative-grounding rule addition under the existing "Agent / grounding" bullet; add `python -m app.seed.embed_seed_data` to Development Commands, alongside the existing `python -m app.seed.seed` line; add `vector_search.py`/`embedding_client.py` to the Project Structure tree
- [ ] Update `docs/reference/seed-patterns.md` with a short new section noting the embedding columns' state (populated only once `embed_seed_data.py` has been run with live credentials; `NULL` by default in a fresh clone/reseed) and the exact `psql` verification query from UAT-4.4, so this stays the single reference for "what's actually true about the seeded data right now"
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 4 status, flagging the same live-credentials-gap caveat Phase 3 used (buildable/tested now; UAT-4.4/4.5 pending GCP setup)
- [ ] Update `.env.example` if any new environment variables are introduced (none are currently planned — embedding calls reuse the exact same `GOOGLE_APPLICATION_CREDENTIALS`/`GCP_PROJECT_ID`/`GCP_REGION` vars Phase 3 already added; confirm no gaps found during implementation)

## Security Considerations

- **No new secrets or credential surface.** `EmbeddingClient` consumes the exact same `GOOGLE_APPLICATION_CREDENTIALS`/`GCP_PROJECT_ID`/`GCP_REGION` settings Phase 3 already introduced — no new environment variables, no new `.gitignore` entries needed.
- **User-supplied text reaches Vertex AI's embedding API.** The `query` argument to `search_customer_reviews` — ultimately derived from the chat user's question, same as every argument to every existing tool — is sent to Vertex AI as embedding input. This is not a new exposure beyond what Phase 3 already established (the full question text is already sent to Gemini for the chat call itself); no additional data is exposed by also sending a substring of it for embedding.
- **`embed_seed_data.py` uses privileged (non-read-only) DB credentials**, matching `seed.py`'s existing precedent, and is explicitly a standalone script, never reachable via any HTTP route or agent tool call — `app/agent/tools/vector_search.py` (the only agent-facing surface this phase adds) exclusively uses `readonly_connection()`. This boundary is enforced by the refactor task in 4.3 (confirm `vector_search.py` never imports `app.db.session`) and mirrors the exact `app/agent/tools/db.py`-is-the-only-DB-entry-point rule already documented in CLAUDE.md.
- **The vector-literal string-formatting approach (`_format_vector_literal`) is a controlled, bind-parameterised construction, not string-interpolated user input.** The *values* going into the literal are floats returned by `EmbeddingClient.embed_texts()` (Vertex AI's own numeric output, never raw user text), and the resulting string is passed as a bind parameter value (`:query_vector`), not spliced into the SQL text itself — the only thing embedded directly in the query *text* is the literal `CAST(:query_vector AS vector)` syntax, which is a fixed, hardcoded string. This is a materially different (and safe) situation from the raw SQL tool's LLM-authored *query shape* risk (ADR-006) — worth stating explicitly so this isn't mistaken for a similar injection surface.
- **No new dependencies** — `google-genai` and `pgvector` were both already vetted and added in Phases 1/3; nothing new to `pip audit` beyond the periodic check CLAUDE.md already calls for.
- No authentication/authorisation changes — still no user accounts, consistent with every prior phase.

## Testability

- **No new user roles this phase** — still the single-persona, no-auth model (master-plan.md §2).
- **No new scheduled/automated feature this phase** — `embed_seed_data.py` is a manually-run, on-demand script (like `seed.py` itself), not a background/scheduled job, so there's no "manual trigger" mechanism to build separately — running it *is* the manual trigger.
- **External integration (Vertex AI embeddings) — the same testability question Phase 3 answered for the chat model, answered here the same way.** `EmbeddingClient` (4.1) is this phase's adapter boundary: everything above it (`vector_search.py`, `tool_registry.py`, `embed_seed_data.py`) is testable via plain `AsyncMock` fixtures with zero GCP dependency, and the adapter's own translation logic is tested against hand-constructed (network-free) real SDK response objects, exactly mirroring `GeminiClient`/ADR-007. The one thing this pattern *cannot* substitute for — real semantic relevance of real embeddings against real review text — is explicitly gated behind live credentials as UAT-4.4/4.5, not silently assumed to work because the mocked/hand-crafted-vector tests pass. This is stated plainly here rather than left implicit, matching Phase 3's own "Testability" section framing.
- **No sandbox/test-mode toggle is being added for Vertex AI embeddings**, consistent with CLAUDE.md's existing stance for the chat model ("no sandbox/test mode needed... normal API usage during development doubles as testing") — once live credentials exist, running `embed_seed_data.py` normally is itself the test.

## Dependencies & Risks

- **Live Vertex AI embedding calls cannot be tested in this implementation environment right now — carried forward from Phase 3, not a new risk but a continuation of the same one.** Everything in this plan except an actual network call to Vertex AI's embedding endpoint is buildable and testable today via `EmbeddingClient`'s adapter/fixture strategy (4.1) and hand-crafted-vector integration tests (4.3). The one thing that genuinely cannot be verified until the user completes `docs/reference/gcp-setup.md`'s checklist: does a *real* embedding call actually populate 154 rows correctly and deterministically, and do the resulting vectors produce *semantically* sensible nearest-neighbour results for a real question? UAT-4.4/4.5 are scoped to close this gap and should not be marked complete until then.
- **The exact `google-genai` SDK method/parameter names for embedding calls are unconfirmed against the installed package version**, mirroring ADR-007's own caveat about the Flash model ID. `client.models.embed_content(...)`/`types.EmbedContentConfig(output_dimensionality=...)` is this plan's best-available expectation at time of writing, not a verified fact — confirm against the installed `google-genai` version's actual API surface during 4.1's implementation, and correct `embedding_client.py`/ADR-008 if the real shape differs.
- **Dimension mismatch is a loud, not silent, failure mode.** If `EMBEDDING_MODEL`/`output_dimensionality` configuration is ever wrong (producing, say, 3072-dimensional vectors instead of 768), `_validate_dimensions()` (4.1) raises a clear `ValueError` before any DB write is attempted, and even if that guard were somehow bypassed, the `vector(768)` column itself would reject the write with a Postgres-level type error — two independent layers, neither silent, so this class of misconfiguration is expected to surface immediately during the first live test run rather than corrupt data quietly.
- **`embed_seed_data.py`'s idempotency (4.2) assumes the embedding model itself is deterministic for identical input** — true for essentially all production embedding models (no temperature/sampling involved, unlike Gemini's chat generation), but this is a property of the live model that can only be confirmed once live credentials exist (UAT-4.4's second-run check). The mocked integration test proves the *script's own logic* introduces no non-determinism; it cannot prove the *model's* determinism.
- **The vector-literal-via-`CAST` binding approach (4.3) has not been executed against a live Postgres+pgvector instance during this planning pass** — it follows pgvector's documented text-input format (`[0.1,0.2,...]`) and should work, but this is exactly the kind of detail worth confirming empirically in the first implementation pass (the first integration test task in 4.3 will surface any issue immediately, since it exercises this exact code path against the real local Postgres instance).
- **No git repository initialized yet** (carried forward, unchanged) — not blocking for implementation.
- **Docker is not installed in this implementation environment** (carried forward, unchanged) — this phase's DB-touching tasks are written generically against whichever local Postgres instance `DATABASE_URL` points at.
