# Ask Sous

## Project Overview

Ask Sous is a solo-built demo of a grounded restaurant-analytics chat agent: a restaurant owner asks natural-language questions about their transaction data and gets answers computed from real numbers (never invented), and can request marketing campaign copy grounded in their brand voice, performance data, and past campaigns. It's a scaled-down but architecturally faithful rebuild of a real production system, built to support concrete, specific interview conversations about the tradeoffs involved — not just to work as a demo. See `docs/definition/master-plan.md` for full product detail.

## Tech Stack Summary

Python 3.12 / FastAPI backend, Postgres 16 + pgvector, Vertex AI SDK (Gemini Flash 2.5 default, Pro-tier escalation), React + Vite + TypeScript frontend with Tailwind/shadcn/ui. Full reference: `docs/definition/stack.md`.

## Project Structure

```
ask-sous/
  backend/
    app/
      main.py              # FastAPI entrypoint
      api/                 # route handlers (chat, campaigns, restaurants)
      agent/                # agent orchestration
        llm_client.py        # GeminiClient — Vertex AI chat/function-calling SDK boundary
        embedding_client.py  # EmbeddingClient — Vertex AI embedding SDK boundary
        tool_registry.py     # INSIGHTS_TOOLS / TOOL_DISPATCH — the six LLM-callable tools
        insights.py          # answer_question() orchestration loop
        tools/              # aggregation tools, raw SQL tool, vector search tool
          db.py               # the ONLY module here permitted to open a DB connection (readonly_connection())
          revenue_summary.py
          item_velocity.py
          period_comparison.py
          cohort_comparison.py
          raw_sql.py          # run_readonly_query() — sqlglot-validated, row-capped, timed-out
          vector_search.py    # search_reviews()/search_similar_campaigns() — pgvector similarity
        routing.py          # model-routing heuristic
        prompts/
      db/
        models.py           # SQLAlchemy models
        session.py
        migrations/         # Alembic
      seed/
        seed.py              # Faker-based seed script, fixed random seed
        generators.py
        embed_seed_data.py   # populates reviews/campaigns.embedding via EmbeddingClient (Phase 4+)
        trickle.py           # optional background trickle inserter (Phase 7)
      core/
        config.py            # env/settings loading (fail-fast Settings, READONLY_DB_ROLE constant)
        paths.py             # REPO_ROOT — single source of truth for locating the repo-root .env
        logging.py           # structlog setup
        responses.py         # success()/error_response() envelope helpers
        errors.py            # global exception handlers
    tests/
      unit/
      integration/
    pyproject.toml
    alembic.ini
  frontend/
    src/
      components/
      pages/
      hooks/
      lib/
    tests/
    package.json
  docker-compose.yml
  .env.example
  docs/
  CLAUDE.md
```

- Path alias: `@/` → `frontend/src/` .
- Python: snake_case for files/functions, PascalCase for classes.
- React: PascalCase component files/names, camelCase functions/variables.

## Development Commands

- `docker-compose up` — start Postgres + backend (requires Docker; see note below).
- `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` — one-time backend environment setup. Requires Python **>=3.12** (whatever `python3` resolves to locally, as long as it satisfies that minimum).
- `cd backend && alembic upgrade head` — run migrations (needs `DATABASE_URL` reachable — either via `docker-compose up` or a local Postgres+pgvector instance).
- `cd backend && python -m app.seed.seed` — seed the database (idempotent, deterministic — see `docs/reference/seed-patterns.md`).
- `cd backend && python -m app.seed.embed_seed_data` — populate `reviews`/`campaigns.embedding` via Vertex AI (requires live GCP credentials — see `docs/reference/gcp-setup.md`; fails cleanly with `AgentUnavailableError` without them).
- `cd backend && pytest` — backend tests.
- `cd backend && ruff check . && ruff format .` — backend lint/format.
- `cd frontend && npm install` — one-time frontend dependency install.
- `cd frontend && npm run dev` — frontend dev server (`http://localhost:5173`).
- `cd frontend && npm run test` — frontend tests (Vitest).
- `cd frontend && npm run build` — type-check + production build.
- `cd frontend && npm run lint` / `npm run format` — Biome check / check --write.
- `pre-commit run --all-files` — lint/format checks via both hooks at once, **once `git init` has been run** (pre-commit needs a `.git` directory; run `pre-commit install` at that point too).

**Local Postgres without Docker:** if Docker isn't available, `brew install postgresql@17 pgvector` (pgvector's Homebrew formula targets Postgres 17/18, not 16, so this diverges from the `pgvector/pgvector:pg16` image `docker-compose.yml` uses — fine for local dev/testing, since the migration SQL itself is version-independent). Create the admin role/database matching your `.env`, then proceed with the commands above.

## Conventions

### API design
- Response shape: `{ "data": ..., "error": null }` or `{ "data": null, "error": { "message": ..., "code": ... } }`.
- Validation via Pydantic models at the API boundary.
- No auth/authorisation on routes — this project has no user accounts (see master-plan.md §2).

### Database
- Table names: plural, snake_case (`restaurants`, `transaction_items`, etc.).
- Primary keys: UUID.
- `created_at` / `updated_at` timestamps on all tables.
- No soft deletes — not needed at this scale.
- Migrations via Alembic (`alembic revision --autogenerate`, review before applying). `app/db/migrations/env.py` imports `app.db.models` explicitly so autogenerate sees registered tables — without it, `Base.metadata` is empty and autogenerate silently produces a no-op migration.
- Closed-set string columns (`size_category`, `payment_type`, `channel`, `source`, etc.) use a `CheckConstraint`, not a native Postgres ENUM — keeps adding a new allowed value a plain migration, no `ALTER TYPE` ceremony.
- The agent's tools connect via a **dedicated read-only Postgres role, `ask_sous_readonly`** (created in migration `0002`, see `docs/decisions/002-readonly-postgres-role.md`) — never the same credentials used by migrations/seed scripts. This is a hard boundary, not a convention to relax under time pressure. Proven by integration test (`backend/tests/integration/test_db_bootstrap.py`), not just asserted. **Concretely, `app/agent/tools/db.py` is the only module in `app/agent/` permitted to open a database connection** (`readonly_connection()`) — every tool function goes through it, and nothing in `app/agent/` ever imports `app/db/session.py`'s admin-credentialed path. A fresh engine is created and disposed per call, not cached — see `docs/decisions/005-readonly-tool-connection-lifecycle.md` for why (asyncpg connections are bound to their creating event loop; Phase 0 already hit and reverted a module-scoped-engine bug for the same reason).
- The seed script (`app/seed/seed.py`/`generators.py`) generates deterministic primary-key UUIDs drawn from its seeded RNG (`uuid.UUID(int=rng.getrandbits(128), version=4)`), not `uuid.uuid4()`, so re-seeding is byte-for-byte reproducible. **This convention is scoped to `seed.py`/`generators.py` only** — Phase 7's live-trickle generator (`trickle.py`) must use genuine `uuid.uuid4()` and must not reuse the fixed seed, since it exists specifically to simulate non-deterministic ongoing activity. See `docs/decisions/004-seed-data-determinism-and-patterns.md`.

### Agent / grounding
- Every agent turn logs: the question, every tool call (with arguments), each tool's raw result, which model handled the turn, and the final answer (via `structlog`). Concretely (Phase 3): `agent_turn_started`, `tool_call_requested`, `tool_call_result`, `agent_turn_model_selected`, `agent_turn_completed`, all correlated by a per-turn `turn_id` bound via `structlog.contextvars.bind_contextvars()` and cleared in a `finally` block — see `backend/app/agent/insights.py`.
- **No naked numbers rule:** the agent must never state a number without a corresponding logged tool call backing it, for that turn. Enforce this in code review. Backed (Phase 3) by a best-effort, non-blocking `_check_grounding()` check that logs a `possible_ungrounded_numeric_answer` warning when an answer contains a digit but no tool was called that turn, plus a test-level guard (`tests/integration/test_grounding_guard.py`) proving the test suite itself would catch a genuinely ungrounded response for data-requiring questions.
- Aggregation tools (Phase 2) and the raw SQL tool (Phase 3, `run_readonly_query()`) both execute parameterised queries only — no dynamic table/column names built from LLM output. The one place a tool selects a SQL fragment by argument value (`cohort_comparison.py`'s `metric` parameter) does so via a small hardcoded allow-list dict with a runtime `ValueError` guard for anything outside it — never via f-string/`.format()` on caller input. Follow this pattern for any future tool that needs the same kind of "pick one of a few fixed expressions" behaviour. The raw SQL tool additionally validates its (partly LLM-authored) query text structurally via `sqlglot` before it ever reaches Postgres — see `docs/decisions/006-raw-sql-tool-safety-mechanism.md`.
- **Pure/impure split** — every `app/agent/tools/` module separates a pure computation function (`_summarize_daily_rows`, `_build_item_velocities`, `_prior_period`/`_compare`, `_ratio`, `_validate_select_only`/`_enforce_row_cap`) that takes plain data and returns a dataclass, no DB/event loop involved, from a thin `async def get_x()` wrapper that fetches rows and delegates to it. Established in Phase 1 (`generators.py`/`seed.py`) and carried forward in Phases 2–3 — keep following it for Phase 4's vector search tool, since it's what makes the fast, DB-free unit-test layer possible at all.
- **`app/agent/llm_client.py` and `app/agent/embedding_client.py` are the only modules in `app/agent/` or `app/api/` permitted to import `google.genai`.** `GeminiClient` accepts and returns only this app's own frozen dataclasses (`ToolDeclaration`, `UserText`/`ModelToolCalls`/`ToolResultsTurn`, `ToolCallRequest`/`FinalAnswer`); `EmbeddingClient.embed_texts()` accepts `list[str]` and returns `list[list[float]]` — neither ever exposes a raw SDK type — so every layer above them (`tool_registry.py`, `insights.py`, `chat.py`, `vector_search.py`, `embed_seed_data.py`) is testable with plain `AsyncMock` and zero GCP dependency. Verify with `grep -rn "from google" app/agent/ app/api/` — it should show hits only in `llm_client.py` and `embedding_client.py`. Both adapters catch `google.auth.exceptions.GoogleAuthError` alongside SDK-level errors when translating to `AgentUnavailableError` — a missing/invalid credentials failure (this environment's current default state) needs the same translation as a rate limit or outage. See `docs/decisions/007-gemini-model-selection-and-client-adapter.md` and `docs/decisions/008-embedding-model-and-client-adapter.md`.
- **Six LLM-callable tools** (`INSIGHTS_TOOLS`/`TOOL_DISPATCH` in `tool_registry.py`): the four Phase 2 aggregation tools, `run_readonly_query` (Phase 3), and `search_customer_reviews` (Phase 4, pgvector similarity search over `reviews.embedding` — see `docs/decisions/009-vector-retrieval-tool-design.md`). Qualitative questions about customer sentiment must go through `search_customer_reviews`, never invented/paraphrased review content — enforced via the system instruction in `app/agent/prompts/insights_system_instruction.py`, same "no naked numbers"-style discipline applied to qualitative claims. `search_similar_campaigns` (also in `vector_search.py`) is built but deliberately **not** registered as an LLM-callable tool — it's a plain function for Phase 5's campaign generation to call directly, not something the model decides to invoke mid-conversation.
- **Access point:** `POST /chat` (`backend/app/api/chat.py`) — request `{restaurant_id, question}`, response `{answer, tool_calls, model}` inside the standard envelope. Checks restaurant existence via `readonly_connection()` before calling `answer_question()`; never imports `llm_client` directly.

### State management (frontend)
- Server state: TanStack Query.
- Client/UI-only state (selected restaurant, panel toggles): React Context or local `useState` — no need for a separate state library at this scale.

### Error handling
- Consistent `{ error: { message, code } }` shape from the API, built via `app.core.responses.success()` / `error_response()` — never construct the envelope dict inline elsewhere.
- `code` values are short, stable, snake_case strings identifying the error kind (not free text) — e.g. `internal_error`, `validation_error`. New error paths should introduce a new `code` value rather than reusing `internal_error` for everything.
- Unhandled exceptions and validation errors are both caught by global handlers (`app.core.errors`) that log full details server-side via `structlog` but return only the generic envelope to the client — internals (stack traces, file paths, query fragments) never leak into a response body.
- Vertex AI failures (rate limits, outages) are caught and surfaced as a clear "agent unavailable" error — never silently swallowed, never retried indefinitely. Concretely (Phase 3): `AgentUnavailableError` → HTTP 503, `code="agent_unavailable"`; `AgentIncompleteError` (the agent ran but didn't converge on an answer within the tool-call round cap) → HTTP 502, `code="agent_incomplete"`. Both handlers in `app.core.errors`, registered in `main.py` alongside the existing two.
- Frontend surfaces errors via inline banners/toasts (shadcn/ui toast component).

### Security
- Secrets (DB URL, GCP service account key path) live in `.env` (gitignored); `.env.example` holds placeholders only.
- GCP service account key file itself is gitignored, never committed.
- Input validation happens at the API boundary (Pydantic) — trust internal function calls beyond that boundary.
- No auth/authz patterns needed (no user accounts).
- Run `pip audit` / `npm audit` periodically; prefer well-maintained, actively-released dependencies.

### Testability
- No test-account matrix needed (single persona, no auth).
- The optional live-trickle generator (Phase 7) is toggled via the `ENABLE_TRICKLE` env var — no manual "fire now" trigger was requested; it runs on its own timer.
- Model routing (Flash vs Pro-tier) is logged per turn — no manual override to force a route; the heuristic is exercised naturally by asking varied questions.
- No sandbox/test mode needed for Vertex AI — normal API usage during development doubles as testing, since there's no cost-sensitive side effect to isolate.

## Documentation Rules

1. **ADRs** — every non-trivial technical/product decision goes in `docs/decisions/`, using `docs/decisions/_template.md`.
2. **Living docs** — when a change affects an existing doc, update it in the same changeset as the code.
3. **Plans before code** — every phase/feature gets a plan in `docs/plans/` before implementation starts.
4. **Changelog** — log notable changes and phase completions in `docs/changelog.md`.
5. **Tests before code (TDD)** — red-green-refactor by default; exceptions for UI layout, config, and scaffolding.

## Testing Rules

- Framework: `pytest` (backend), `Vitest` + React Testing Library (frontend), `Playwright` for E2E (introduced from Phase 6 once a UI exists).
- Co-location: backend tests in `backend/tests/{unit,integration}/`; frontend tests co-located or in `frontend/tests/`, mirroring `src/`.
- **Testing depth: Practical** — critical paths and happy paths well covered, no coverage-number chasing on trivial code. **Exception:** Phase 1 (Data Layer) and Phase 2 (Aggregation Tools) are held to a stricter bar, since their correctness is the project's core success metric (master-plan.md §9) — verify against known, hand-computable seed-data patterns, not just "doesn't crash."

## Ways of Working

- **Collaboration style:** Collaborative — review plans before implementation, see reasoning, approve changes before large chunks of work proceed.
- **Git workflow:** Direct to main — solo project, no branch/merge overhead.
- **Team:** Solo.
- **Testing depth:** Practical — see Testing Rules above for the Phase 1/2 exception.

## Key Files

- `docs/definition/master-plan.md` — product specification.
- `docs/definition/implementation-plan.md` — phased build plan (this is the authoritative task breakdown).
- `docs/definition/stack.md` — full tech stack reference.
- `docs/definition/design-guidelines.md` — design system (populated by `/designer`, run after this).
- `docs/decisions/` — ADRs.
- `docs/reference/seed-patterns.md` — the seeded ground truth (restaurant profiles, deliberate patterns, exact verification queries) every later phase checks its numbers against.

## Workflow

See `docs/process.md` for the full project workflow and available skills. Phases 0–2 (Project Foundation, Data Layer, Aggregation Tools) are complete — next up is Phase 3 (Agent Core / Insights Q&A) via `/implement`. If ever unsure what to do next, run `/status`.

Note: version control (`git init`) has not been set up yet in this repo — do so before continuing if you want commit history from here forward; `.gitignore` and `.pre-commit-config.yaml` are already in place and ready for it.
