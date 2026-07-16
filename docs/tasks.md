# Ask Sous — Task List

Status indicators: ⬜ Not Started · 🟧 In Progress · 🟩 Done · 🟥 Blocked

---

## Phase 0: Project Foundation

### 0.1 Repository & tooling

- 🟩 Create the monorepo directory skeleton (`backend/app/{api,agent,agent/tools,agent/prompts,db,seed,core}` with `__init__.py` stubs)
- 🟩 Create `backend/pyproject.toml` with Phase-0 dependencies and `[tool.ruff]` config
- 🟩 Scaffold `frontend/` via Vite React-TS template and remove default boilerplate
- 🟩 Install Biome and create `frontend/biome.json`
- 🟩 Create root `.pre-commit-config.yaml` (Ruff + Biome hooks, not installed this session)
- 🟩 Add a Conventional Commits note to `README.md`
- 🟩 Refactor: confirm `backend/app/__init__.py` files don't shadow stdlib names, `frontend/` builds cleanly

### 0.2 Environment & secrets

- 🟩 Create root `.env.example` with all Phase-0 variables and inline comments
- 🟩 Create root `.gitignore` covering secrets, key files, and standard build/cache artefacts
- 🟩 Create `frontend/.env.example` with `VITE_API_BASE_URL`
- 🟩 Write `docs/reference/gcp-setup.md` as a manual, one-time checklist

### 0.3 Database

- 🟩 Write a failing integration test asserting the `vector` extension is present after migrations run
- 🟩 Implement migration `0001_enable_vector_extension`
- 🟩 Write a failing integration test asserting the `ask_sous_readonly` role exists and can `SELECT`
- 🟩 Write a failing integration test asserting `ask_sous_readonly` is rejected on `CREATE TABLE`/`INSERT`/`DROP`
- 🟩 Implement migration `0002_create_readonly_role`
- 🟩 Refactor: extract shared `backend/tests/integration/conftest.py` fixture (admin + readonly engines)
- 🟩 Create `docker-compose.yml` (postgres + backend services)
- 🟩 Create `backend/Dockerfile` and `backend/.dockerignore`
- 🟩 Initialise Alembic (async template) under `backend/app/db/migrations/`
- 🟩 Create `backend/app/db/base.py` (shared declarative `Base`)

### 0.4 Backend shell

- 🟩 Write failing unit tests for `Settings` fail-fast config loading
- 🟩 Implement `backend/app/core/config.py`
- 🟩 Write a failing integration test for `GET /health` exact envelope shape
- 🟩 Implement `backend/app/api/health.py`, `backend/app/core/responses.py`, wire into `main.py`
- 🟩 Write failing unit tests for global exception handlers (unhandled + validation)
- 🟩 Implement `backend/app/core/errors.py`, register handlers in `main.py`
- 🟩 Create `backend/app/core/logging.py`, call `configure_logging()` from `main.py`
- 🟩 Create `backend/app/db/session.py` (async engine, sessionmaker, `get_db()`)
- 🟩 Refactor: confirm `health.py`/`errors.py` reuse `responses.py` helpers exclusively

### 0.5 Frontend shell

- 🟩 Write failing `HealthCheckPage` test — loading then success pill
- 🟩 Write failing `HealthCheckPage` test — error pill on rejection
- 🟩 Implement `HealthCheckPage.tsx`, `lib/api.ts`, wire `App.tsx`/`main.tsx`
- 🟩 Run `shadcn@latest init`, install `lucide-react` and `@tanstack/react-query`
- 🟩 Add Google Fonts `<link>` tags to `index.html`
- 🟩 Define design-token CSS custom properties in `index.css`, map in Tailwind config
- 🟩 Create `frontend/src/lib/theme.ts`, call `bootstrapTheme()` from `main.tsx`
- 🟩 Refactor: extract `StatusTag.tsx` (used from the start, given the loading/success/error branching)

### 0.X Testing (cross-cutting)

- 🟥 End-to-end `GET /health` check against the full `docker-compose` stack — **blocked: Docker is not installed in this environment.** Verified the equivalent instead: `uvicorn` run as a real standalone process (not in-process `ASGITransport`), hit via `curl` — exact envelope shape confirmed live.
- 🟩 Confirm read-only role tests pass against the same Postgres instance the backend connects to (verified against a local Homebrew Postgres 17 + pgvector instance, since Docker is unavailable — see note in completion summary)
- 🟧 Manual verification pass — completed: `alembic upgrade head` x2 (idempotent), psql readonly-role rejection check, `curl /health`, `ruff check`/`format`, `biome check`, `pytest`, `npm run test`/`build`, dark/light mode visual check via Playwright, backend-down error-pill check, `.gitignore` audit. **Not completed:** `docker-compose up` (Docker not installed).

### 0.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-0.1, UAT-0.2, UAT-0.3
- 🟩 Update `docs/changelog.md` with Phase 0 completion summary
- 🟩 Write `docs/decisions/002-readonly-postgres-role.md`
- 🟩 Update `CLAUDE.md` (name `ask_sous_readonly` explicitly, confirm Development Commands, document error `code` convention)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 0 complete

---

## Phase 1: Data Layer

### 1.1 Schema

- 🟩 Add `pgvector` Python package to `backend/pyproject.toml` runtime dependencies
- 🟩 Write failing integration test asserting all six tables + key column types exist after migration
- 🟩 Write failing integration test asserting a smoke insert per table succeeds and FK violations are enforced
- 🟩 Write failing integration test (parametrized) asserting `ask_sous_readonly` can `SELECT` from all six tables and is rejected on `INSERT`
- 🟩 Implement `backend/app/db/models.py` (`TimestampMixin` + six models)
- 🟩 Generate and hand-correct the Alembic migration (`create_core_schema`)
- 🟩 Run `alembic upgrade head`; confirm all three tests above pass
- 🟩 Refactor: constraint/index naming consistency, no model re-derives `Base`

### 1.2 Seed script

- 🟩 Add `Faker` to `backend/pyproject.toml` runtime dependencies
- 🟩 Write failing unit tests (`test_seed_generators.py`) — determinism, 90-day window, Golden Skillet Tuesday suppression, Casa Verde control, Bella Notte trend, Sakura Table premium ticket, total_amount invariant
- 🟩 Implement `backend/app/seed/generators.py` (constants, profiles, baseline tables, all generator functions)
- 🟩 Implement `backend/app/seed/seed.py` (`seed_database()`, `main()`, bulk Core-level inserts)
- 🟩 Write failing integration test asserting row counts/coverage after `seed_database()`
- 🟩 Write failing integration test asserting `seed_database()` idempotency (identical counts + identical Golden Skillet revenue across two runs)
- 🟩 Write failing integration tests asserting all three deliberate patterns via direct SQL against seeded DB
- 🟩 Fix any Decimal/rounding issues surfaced by the DB round-trip (none needed — passed first run)
- 🟩 Write `docs/reference/seed-patterns.md`
- 🟩 Refactor: `seed.py` contains zero statistical logic; constants defined once in `generators.py`

### 1.X Testing (cross-cutting)

- 🟩 Full pipeline test: fresh `alembic upgrade head` + `seed_database()` in one ordered run
- 🟩 Confirm `ask_sous_readonly` can read non-empty seeded data end-to-end
- 🟩 Manual verification pass — `alembic upgrade head` x2 (no-op second run), seed script x2 (identical row counts: 5/59/36877/93866/138/16 both times), psql pattern queries (all three patterns confirmed with real numbers — see seed-patterns.md), psql readonly check (SELECT works, INSERT rejected with "permission denied for table restaurants"), `ruff check`/`format` clean, `pytest` 44/44 passing

### 1.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-1.1 through UAT-1.4
- 🟩 Update `docs/changelog.md` with Phase 1 completion summary
- 🟩 Write `docs/decisions/003-vector-column-dimensionality.md`
- 🟩 Write `docs/decisions/004-seed-data-determinism-and-patterns.md`
- 🟩 Update `CLAUDE.md` (seed-patterns.md in Key Files, CHECK-constraint convention, deterministic-UUID convention scoped away from Phase 7)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 1 complete

---

## Phase 2: Aggregation Tools

### 2.1 Read-only DB connection path for tools

- 🟩 Write failing unit test for `Settings` fail-fast on missing `READONLY_DB_PASSWORD`
- 🟩 Add `readonly_db_password: str` to `Settings`
- 🟩 Write failing unit tests for `readonly_database_url()` (correct role/password swap, differs from admin URL)
- 🟩 Implement `backend/app/agent/tools/db.py` (`readonly_database_url()`, `readonly_connection()`)
- 🟩 Write failing integration test: `readonly_connection()` reports `current_user`, can SELECT, rejected on INSERT
- 🟩 Extend `conftest.py` with `seeded_restaurants` fixture
- 🟩 Refactor: `db.py` imports `READONLY_DB_ROLE` from config, no `app/agent/` file imports `app.db.session`

### 2.2 Revenue summary tool

- 🟩 Write failing unit tests for `_summarize_daily_rows()` (sums, average ticket, empty-range zero case)
- 🟩 Implement `_summarize_daily_rows()`
- 🟩 Write failing integration test for `get_revenue_summary()` zero-transaction range
- 🟩 Implement `get_revenue_summary()`
- 🟩 Refactor: module-level SQL constant, thin async wrapper

### 2.3 Item velocity tool

- 🟩 Write failing unit tests for `_window_midpoint()`
- 🟩 Implement `_window_midpoint()`
- 🟩 Write failing unit tests for `_build_item_velocities()` (up/down/flat/undefined-change/top_n)
- 🟩 Implement `_build_item_velocities()`
- 🟩 Write failing integration test for `get_item_velocity()` empty-match case
- 🟩 Implement `get_item_velocity()`
- 🟩 Refactor: confirm `menu_item_name` is a genuine bind parameter

### 2.4 Period comparison tool

- 🟩 Write failing unit tests for `_prior_period()` (1-day and 7-day periods)
- 🟩 Implement `_prior_period()`
- 🟩 Write failing unit tests for `_compare()` (increase/decrease/zero-prior)
- 🟩 Implement `_compare()`
- 🟩 Write failing integration test for `compare_periods()` zero-transaction case
- 🟩 Implement `compare_periods()`
- 🟩 Refactor: confirm no SQL of its own, only orchestrates `get_revenue_summary()`

### 2.5 Peer/cohort comparison tool

- 🟩 Write failing unit tests for `_ratio()`
- 🟩 Implement `_ratio()`
- 🟩 Write failing unit test: invalid `metric` raises `ValueError` before any DB call
- 🟩 Implement allow-list validation
- 🟩 Write failing integration test for `get_cohort_comparison()` zero-transaction case
- 🟩 Implement full `get_cohort_comparison()`
- 🟩 Refactor: confirm `_METRIC_EXPRESSIONS` is the only argument-selected SQL fragment site, with explanatory comment

### 2.6 Correctness verification against seed patterns

- 🟩 Read-only boundary tests per tool module (spy on `readonly_connection`)
- 🟩 Golden Skillet Tuesday slowdown via `get_revenue_summary()`
- 🟩 Golden Skillet Tuesday slowdown via `compare_periods()`
- 🟩 Casa Verde control via `get_revenue_summary()`
- 🟩 Bella Notte Truffle Fries trend via `get_item_velocity()` halves
- 🟩 Bella Notte Truffle Fries trend via `get_item_velocity()` thirds (matches seed-patterns.md exactly)
- 🟩 Sakura Table premium ticket via `get_cohort_comparison()`
- 🟩 Control contrast via `get_cohort_comparison()`
- 🟩 `total_revenue`/`transaction_count` metric sanity checks
- 🟩 Refactor: inline comments on every threshold explaining its seed-patterns.md margin

### 2.X Testing (cross-cutting)

- 🟩 Full-suite pass, no regressions
- 🟩 Cross-tool consistency: `get_revenue_summary()` total equals sum of daily breakdown
- 🟩 Cross-tool consistency: `compare_periods()` current matches direct `get_revenue_summary()` call
- 🟩 Manual verification pass (REPL spot-check vs seed-patterns.md, grep for admin-session imports, ruff, pytest)

### 2.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-2.1 through UAT-2.4
- 🟩 Update `docs/changelog.md` with Phase 2 completion summary
- 🟩 Write `docs/decisions/005-readonly-tool-connection-lifecycle.md`
- 🟩 Update `CLAUDE.md` (db.py as the boundary's concrete implementation, pure/impure split convention)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 2 complete

---

## Phase 3: Agent Core (Insights Q&A)

### 3.1 Agent setup — Vertex AI client, tool schemas, raw SQL tool, response assembly

- 🟩 Add `google-genai` and `sqlglot` to `backend/pyproject.toml` dependencies; `pip install -e ".[dev]"` to pick them up
- 🟩 Write a failing unit test (`test_llm_client.py`) asserting `GeminiClient()` constructs `genai.Client` with `vertexai=True` and `project`/`location` from `Settings`
- 🟩 Implement `GeminiClient.__init__` in `app/agent/llm_client.py`
- 🟩 Write a failing unit test asserting `GeminiClient.generate_turn()` translates a hand-built `GenerateContentResponse` (function-call Part → `list[ToolCallRequest]`; text Part → `FinalAnswer`)
- 🟩 Implement translation logic in `generate_turn()`
- 🟩 Write failing unit tests (`test_tool_registry.py`) for the five `FunctionDeclaration`s in `INSIGHTS_TOOLS`
- 🟩 Implement `INSIGHTS_TOOLS`/`TOOL_DISPATCH` in `app/agent/tool_registry.py`
- 🟩 Write failing unit tests for `_to_jsonable()` (Decimal/date/UUID serialization, Decimal → exact string)
- 🟩 Implement `_to_jsonable()`
- 🟩 Write failing unit tests for each tool's `parse_args()` (valid + invalid cases)
- 🟩 Implement each `parse_args()`
- 🟩 Write failing unit tests (`test_raw_sql_validation.py`) for `_validate_select_only()` (SELECT passes; DROP/UPDATE/INSERT INTO/CTE-hidden-DELETE raise; bind params don't confuse it)
- 🟩 Implement `_validate_select_only()`
- 🟩 Write failing unit tests for `_enforce_row_cap()` (wraps query, caps existing LIMIT too)
- 🟩 Implement `_enforce_row_cap()`
- 🟩 Write a failing integration test (`test_raw_sql_integration.py`) for `run_readonly_query()` against real seeded DB; validation-before-DB-call test
- 🟩 Implement `run_readonly_query()`
- 🟩 Write a failing integration test asserting row-cap truncation with `truncated=True`
- 🟩 Implement/confirm the cap
- 🟩 Write failing unit tests (`test_insights_loop.py`) for `answer_question()` orchestration (single-round, two-round, tool-error, round-cap-exceeded cases)
- 🟩 Implement `answer_question()` in `app/agent/insights.py`
- 🟩 Refactor: confirm only `llm_client.py` imports `google.genai`

### 3.2 Grounding & audit logging

- 🟩 Write a failing unit test (`test_insights_logging.py`) asserting all five structured log events are emitted per turn
- 🟩 Wire up logging call sites in `answer_question()`
- 🟩 Write a failing unit test asserting `turn_id` contextvar binding/clearing (including on `AgentIncompleteError`)
- 🟩 Implement `bind_contextvars`/`try`/`finally`/`clear_contextvars`
- 🟩 Write failing unit tests for `_check_grounding()`
- 🟩 Implement `_check_grounding()`, wire in `possible_ungrounded_numeric_answer` warning
- 🟩 Write the failing guard test (`test_grounding_guard.py`) for ≥3 data-requiring questions
- 🟩 Confirm guard test passes for good scenario, fails for zero-tool-call scenario
- 🟩 Refactor: confirm all `app/agent/` logger calls use structured kwargs, not f-strings

### 3.3 Access point — `/chat` API endpoint

- 🟩 Write a failing integration test (`test_chat_endpoint.py`) for `POST /chat` happy path
- 🟩 Implement `/chat` route in `app/api/chat.py`; register router in `main.py`
- 🟩 Write a failing test for non-existent `restaurant_id` → 404 `restaurant_not_found`
- 🟩 Implement existence check
- 🟩 Write a failing test for malformed `restaurant_id` → 422
- 🟩 Confirm passes via existing validation handler
- 🟩 Write a failing unit test (`test_agent_exceptions.py`) for SDK error → `AgentUnavailableError` translation
- 🟩 Implement catch/translate/re-raise in `generate_turn()`
- 🟩 Write a failing integration test for `AgentUnavailableError` → 503 `agent_unavailable`
- 🟩 Implement `agent_unavailable_exception_handler`, register it
- 🟩 Write a failing integration test for `AgentIncompleteError` → 502 `agent_incomplete`
- 🟩 Implement `agent_incomplete_exception_handler`, register it
- 🟩 Refactor: confirm `chat.py` only calls `answer_question()`, never imports `llm_client` directly

### 3.X Testing (cross-cutting)

- 🟩 Full-suite pass, no regressions
- 🟩 End-to-end mocked flow: `/chat` → real Phase 2 tool → real DB → real logging → real envelope
- 🟩 Malformed-model-output resilience test
- 🟩 `ruff check . && ruff format --check .`
- 🟩 Manual: inspect full `/chat` JSON response with mocked client
- 🟩 Manual: read one full turn's structlog output end-to-end

### 3.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-3.1 through UAT-3.6
- 🟩 Update `docs/changelog.md` with Phase 3 completion summary
- 🟩 Write `docs/decisions/006-raw-sql-tool-safety-mechanism.md`
- 🟩 Write `docs/decisions/007-gemini-model-selection-and-client-adapter.md`
- 🟩 Update `CLAUDE.md` (llm_client.py SDK boundary, raw SQL validation, new error codes, `/chat` endpoint)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 3 status (with live-credentials caveat)
- 🟩 Update `.env.example` if new env vars are introduced (none needed — confirmed)

---

## Phase 4: Vector Retrieval

### 4.1 `EmbeddingClient` — a second Vertex AI adapter

- 🟩 Write a failing unit test (`test_embedding_client.py`) for `EmbeddingClient()` construction (mirrors `GeminiClient`'s test)
- 🟩 Implement `EmbeddingClient.__init__` in `app/agent/embedding_client.py`
- 🟩 Write a failing unit test asserting `embed_texts()` translates a hand-built SDK response into `list[list[float]]`, order-preserving
- 🟩 Implement the translation logic
- 🟩 Write a failing unit test for SDK error → `AgentUnavailableError` translation
- 🟩 Implement catch/translate/re-raise
- 🟩 Write failing unit tests for `_validate_dimensions()`
- 🟩 Implement `_validate_dimensions()`, wire into `embed_texts()`
- 🟩 Write a failing unit test asserting mock-level determinism for identical input
- 🟩 Confirm passes with existing implementation
- 🟩 Refactor: confirm `grep -rn "from google" app/agent/ app/api/` shows hits only in `llm_client.py` and `embedding_client.py`

### 4.2 Seed-time embedding population script

- 🟩 Write failing unit tests (`test_embed_seed_data.py`) for `_chunk()`
- 🟩 Implement `_chunk()`
- 🟩 Write failing unit tests for `_build_update_payloads()`
- 🟩 Implement `_build_update_payloads()`
- 🟩 Write a failing integration test for `embed_and_store_reviews()` (mocked `EmbeddingClient`, real seeded DB, 138 rows updated)
- 🟩 Implement `embed_and_store_reviews()`
- 🟩 Write the equivalent test for `embed_and_store_campaigns()` (16 rows)
- 🟩 Implement `embed_and_store_campaigns()`
- 🟩 Write a failing integration test asserting idempotency across two runs
- 🟩 Confirm passes with existing implementation
- 🟩 Refactor: confirm `embed_seed_data.py` uses the privileged session path (never `readonly_connection`), with an explicit spy test

### 4.3 Vector similarity search — the retrieval tool

- 🟩 Write failing unit tests (`test_vector_search.py`) for `_format_vector_literal()`
- 🟩 Implement `_format_vector_literal()`
- 🟩 Write failing unit tests for `_clamp_top_k()`
- 🟩 Implement `_clamp_top_k()`
- 🟩 Write failing unit tests for `search_reviews()`/`search_similar_campaigns()` (mocked embedding client + DB fetch step)
- 🟩 Implement `search_reviews()`/`search_similar_campaigns()`
- 🟩 Write a failing integration test with hand-crafted embedded vectors proving real pgvector ordering (setup/teardown fixture)
- 🟩 Implement/confirm passes
- 🟩 Write a failing integration test proving restaurant scoping is genuinely enforced
- 🟩 Implement/confirm the scoping clause
- 🟩 Write a failing integration test asserting empty-embeddings state returns empty matches, not an error
- 🟩 Confirm passes with existing implementation
- 🟩 Write failing unit tests extending `test_tool_registry.py` for the sixth tool (`search_customer_reviews`)
- 🟩 Implement the registration in `tool_registry.py`
- 🟩 Write a failing unit test for `search_customer_reviews`'s `parse_args`
- 🟩 Implement `parse_args`
- 🟩 Write a failing unit test extending `test_insights_system_instruction.py` for qualitative-grounding guidance
- 🟩 Implement the system instruction update
- 🟩 Refactor: confirm `vector_search.py` only uses `readonly_connection()`; confirm `search_similar_campaigns` stays unregistered this phase

### 4.X Testing (cross-cutting)

- 🟩 Full-suite pass, no regressions
- 🟩 End-to-end mocked flow: `/chat` → `search_customer_reviews` tool call → real pgvector query → real logging → real envelope
- 🟩 Confirm `test_grounding_guard.py` still passes unmodified
- 🟩 `ruff check . && ruff format --check .`
- 🟩 Manual: `/chat` qualitative question with hand-embedded reviews, inspect JSON response
- 🟩 Manual: confirm `embed_seed_data.py` fails fast and clearly with placeholder credentials (fixed a real gap: added `GoogleAuthError` to both adapters' caught exception types, since `DefaultCredentialsError` wasn't previously translated to `AgentUnavailableError`)

### 4.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-4.1 through UAT-4.5
- 🟩 Update `docs/changelog.md` with Phase 4 completion summary
- 🟩 Write `docs/decisions/008-embedding-model-and-client-adapter.md`
- 🟩 Write `docs/decisions/009-vector-retrieval-tool-design.md`
- 🟩 Update `CLAUDE.md` (embedding_client.py SDK boundary, sixth tool, new dev command, project structure)
- 🟩 Update `docs/reference/seed-patterns.md` with embedding-column state notes
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 4 status (with live-credentials caveat)
- 🟩 Update `.env.example` if new env vars are introduced (none needed — confirmed)

## Phase 5: Campaign Generation

### 5.1 Model routing (insights loop)

- 🟩 Write failing unit tests for `_select_model` (default Flash, threshold escalation, keyword escalation, case-insensitivity)
- 🟩 Implement `_select_model` and `PRO_MODEL` constant
- 🟩 Write a failing unit test asserting a 4th-round tool-calling turn escalates to `PRO_MODEL`
- 🟩 Wire `_select_model` into `answer_question()`'s loop
- 🟩 Update `agent_turn_model_selected` log call with `routing_reason`
- 🟩 Write a failing unit test asserting the keyword path escalates a single-round turn
- 🟩 Confirm/update existing Phase 3 tests that assumed a hardcoded model

### 5.2 Brand voice lookup

- 🟩 Write a failing unit test for `get_brand_voice_guide` (found + not-found cases)
- 🟩 Implement `get_brand_voice_guide` in `app/agent/tools/restaurant_lookup.py`

### 5.3 Campaign system instruction

- 🟩 Write a failing unit test for `build_campaign_system_instruction` (with examples, without examples)
- 🟩 Implement `build_campaign_system_instruction`

### 5.4 Campaign generation orchestration

- 🟩 Write a failing unit test for `generate_campaign` (happy path, mocked dependencies)
- 🟩 Implement `generate_campaign` in `app/agent/campaigns.py`
- 🟩 Write a failing unit test asserting zero-match retrieval still succeeds
- 🟩 Write a failing unit test asserting audit log events are emitted with expected fields

### 5.5 `/campaigns` API endpoint

- 🟩 Write a failing integration test for the endpoint (404 + success shape)
- 🟩 Implement `app/api/campaigns.py` and register the router in `app/main.py` (also extracted a shared `restaurant_exists()` helper into `restaurant_lookup.py`, replacing the duplicated private helper in both `chat.py` and `campaigns.py`)
- 🟩 Write a failing end-to-end integration test against the seeded test DB
- 🟩 Implement/wire whatever the end-to-end test reveals is still missing (nothing further needed)

### 5.X Testing (cross-cutting)

- 🟩 Full-suite pass, no regressions (217 passed)
- 🟩 `ruff check . && ruff format --check .`
- 🟩 Manual: trace one campaign generation call's log lines end-to-end (traced via `test_campaigns.py::test_generate_campaign_emits_audit_log_events` — confirms `campaign_turn_started` → `campaign_examples_retrieved` → `campaign_turn_completed` with expected fields; real Vertex AI log content deferred to UAT-5.1)

### 5.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-5.1 through UAT-5.6
- 🟩 Update `docs/changelog.md` with Phase 5 completion summary
- 🟩 Write `docs/decisions/010-model-routing-heuristic.md`
- 🟩 Update `CLAUDE.md` (new `/campaigns` endpoint, `restaurant_lookup.py`, routing heuristic summary, corrected stale `routing.py` reference)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 5 status
- 🟩 Update `.env.example` if new env vars are introduced (none needed — confirmed)

## Phase 6: Frontend

### 6.0 Backend: real streaming for `/chat`

- 🟩 Write failing unit test for `_iter_in_thread()` (order preserved, mid-iteration exception propagates)
- 🟩 Implement `_iter_in_thread()`
- 🟩 Write failing unit tests for `GeminiClient.generate_turn_stream()` (text-only chunks, tool-call chunks, mid-stream SDK error)
- 🟩 Implement `generate_turn_stream()`
- 🟩 Write failing unit tests for `answer_question_stream()` (single-round streaming, multi-round tool dispatch, round-cap)
- 🟩 Implement `answer_question_stream()` (factored out shared `_resolve_tool_call_round()` helper with `answer_question()`)
- 🟩 Write failing integration tests for the SSE `/chat` endpoint (happy path + mid-stream failure)
- 🟩 Implement the SSE endpoint (also updated 3 pre-existing `/chat` integration tests to the new streaming contract)
- 🟩 Write failing integration test for `GET /restaurants`
- 🟩 Implement `GET /restaurants`
- 🟩 Write `docs/decisions/011-sse-streaming-and-mid-stream-errors.md`

### 6.1 Chat interface

- 🟩 Write failing Vitest test for the SSE-over-fetch parser in `api.ts`
- 🟩 Implement `streamChat()`
- 🟩 Write failing RTL tests for `ChatMessage`, `CitationChip`, `ThinkingIndicator`
- 🟩 Implement those components
- 🟩 Write failing RTL tests for `ChatPage`
- 🟩 Implement `ChatPage`

### 6.2 Restaurant switcher

- 🟩 Write failing Vitest test for `getRestaurants()`
- 🟩 Implement it
- 🟩 Write failing tests for the restaurant context
- 🟩 Implement the context
- 🟩 Write failing RTL tests for `RestaurantSwitcher`
- 🟩 Implement `RestaurantSwitcher` (native `<select>` instead of a headless dropdown primitive — simpler, fully accessible, far more reliable to test)

### 6.3 Campaigns panel

- 🟩 Write failing Vitest test for `generateCampaign()`
- 🟩 Implement it
- 🟩 Write failing RTL tests for `CampaignsPanel`
- 🟩 Implement `CampaignsPanel`

### 6.4 App shell and design system application

- 🟩 Write failing RTL tests for `AppShell`
- 🟩 Implement `AppShell` (nav items are in-page view toggles, not router links — no router in this stack; chat/campaigns render together on desktop per the split-view design, nav toggling only matters at the mobile breakpoint)
- 🟩 Wire `App.tsx` to mount it (restaurants loaded via `useQuery`, loading/error states, `HealthCheckPage` kept but no longer the root)
- 🟩 Manual pass against `docs/definition/design-system.html` (real browser via Playwright MCP against the live backend/DB — confirmed sidebar/split-view layout, restaurant switcher populated with all 5 seeded restaurants, chat thinking indicator + error banner, campaigns empty state + loading + error states, and the exact "before-first-chunk failure → 503 JSON" path from ADR-011. Found and fixed a real bug: switching restaurants didn't reset `ChatPage`/`CampaignsPanel` state — fixed via a `key={selectedRestaurant.id}` remount in `App.tsx`, with a regression test)

### 6.X Testing (cross-cutting)

- 🟩 Full-suite pass (backend + frontend), no regressions
- 🟩 `ruff check . && ruff format --check .` (backend), `npm run lint` (frontend)
- 🟩 Manual verification pass (see plan's Manual Verification checklist — done via Playwright MCP against the real running backend/DB; dark/light OS-preference toggle and mobile-width resize not explicitly exercised, everything else was)

### 6.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-6.1 through UAT-6.5 (plus an explicit note on the Playwright-automation scope trade-off)
- 🟩 Update `docs/changelog.md` with Phase 6 completion summary
- 🟩 Write `docs/decisions/011-sse-streaming-and-mid-stream-errors.md`
- 🟩 Update `CLAUDE.md` (`/restaurants` endpoint, SSE `/chat` contract change, frontend structure, restaurant-switch remount note)
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 6 status

## Phase 7: Polish (post-MVP)

### 7.1 Live-trickle generator

- 🟩 Write failing integration test for `insert_trickle_transaction()`
- 🟩 Implement `insert_trickle_transaction()`
- 🟩 Write failing integration test for `run_trickle_loop()`
- 🟩 Implement `run_trickle_loop()`
- 🟩 Write failing test asserting the lifespan doesn't start the loop when `ENABLE_TRICKLE=false`
- 🟩 Wire the lifespan in `main.py`

### 7.2 Dashboard

- 🟩 Write failing integration test for `GET /dashboard`
- 🟩 Implement the endpoint, register the router
- 🟩 Write failing Vitest test for `getDashboard()`
- 🟩 Implement it
- 🟩 Write failing RTL tests for `DashboardPage`
- 🟩 Implement `DashboardPage`
- 🟩 Write failing RTL test for `AppShell`'s enabled Dashboard nav item
- 🟩 Implement the `AppShell` change, wire `DashboardPage` into `App.tsx`

### 7.X Testing (cross-cutting)

- 🟩 Full-suite pass (backend + frontend), no regressions (238 backend + 44 frontend, after code-review fixes)
- 🟩 `ruff check . && ruff format --check .` (backend), `npm run lint` (frontend)
- 🟩 Manual verification pass (real browser via Playwright MCP + a live `run_trickle_loop()` run against the real DB — confirmed real transactions inserted with genuine current timestamps, dashboard KPIs/trend/top-items correct. Found and fixed two real bugs: unrounded Decimal KPI values rendering with 20+ digits, and revenue-trend bars rendering with zero height due to a CSS percentage-height parent-sizing gotcha — both fixed with regression tests)

### 7.Y Documentation

- 🟩 Update `docs/uat.md` with UAT-7.1 through UAT-7.4
- 🟩 Update `docs/changelog.md` with Phase 7 completion summary
- 🟩 Write `docs/decisions/012-live-trickle-generator.md` (trickle generator + Recharts-vs-CSS-bars reconciliation)
- 🟩 Update `CLAUDE.md`
- 🟩 Update `docs/definition/implementation-plan.md` to mark Phase 7 status
