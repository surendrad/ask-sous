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
      api/                 # route handlers (chat, campaigns, restaurants, dashboard)
      agent/                # agent orchestration
        llm_client.py        # GeminiClient — Vertex AI chat/function-calling SDK boundary; FLASH_MODEL/PRO_MODEL
        embedding_client.py  # EmbeddingClient — Vertex AI embedding SDK boundary
        tool_registry.py     # INSIGHTS_TOOLS / TOOL_DISPATCH — the eleven LLM-callable tools
        insights.py          # answer_question() orchestration loop + _select_model() routing heuristic
        campaigns.py         # generate_campaign() — agentic tool-calling loop, always PRO_MODEL (ADR-016)
        tools/              # aggregation tools, raw SQL tool, vector search tool
          db.py               # the ONLY module here permitted to open a DB connection (readonly_connection())
          revenue_summary.py
          weekday_performance.py # get_weekday_performance() — revenue/count/avg ticket grouped by weekday (ADR-016)
          item_velocity.py
          period_comparison.py
          cohort_comparison.py
          raw_sql.py          # run_readonly_query() — sqlglot-validated, row-capped, timed-out
          vector_search.py    # search_reviews()/search_similar_campaigns() — pgvector similarity
          restaurant_lookup.py # get_brand_voice_guide(), restaurant_exists(), list_restaurants() — shared by /chat, /campaigns, /dashboard
          locations_comparison.py # compare_locations() — multi-restaurant revenue comparison (Phase 8)
          campaign_performance.py # list_campaigns()/get_campaign_performance() — attributed vs. baseline revenue (Phase 8)
          upsell_metrics.py   # get_upsell_metrics() — designated add-on attach rate/revenue (Phase 8)
        prompts/
          insights_system_instruction.py
          campaign_system_instruction.py
      db/
        models.py           # SQLAlchemy models
        session.py
        migrations/         # Alembic
      seed/
        seed.py              # Faker-based seed script, fixed random seed
        generators.py
        embed_seed_data.py   # populates reviews/campaigns.embedding via EmbeddingClient (Phase 4+)
        trickle.py           # background trickle inserter, started from main.py's lifespan when ENABLE_TRICKLE=true (Phase 7)
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
      App.tsx              # root: loads restaurants, mounts AppShell (Phase 6)
      components/
        AppShell.tsx          # 224px sidebar + chat/campaigns split + full-width Dashboard view (design-guidelines.md §5)
        RestaurantSwitcher.tsx  # checkbox multi-select dropdown, not a headless dropdown lib — see CLAUDE.md note below
        ChatMessage.tsx, CitationChip.tsx, ThinkingIndicator.tsx
      pages/
        ChatPage.tsx          # drives streamChat(); renders incrementally as text_chunk events arrive
        CampaignsPanel.tsx    # plain request/response — /campaigns is not streamed
        DashboardPage.tsx     # KPIs + CSS-drawn charts (Phase 7) — full-width view, not part of the split
      lib/
        api.ts                # streamChat() (SSE-over-fetch), getRestaurants(), generateCampaign(), getDashboard()
        restaurant-context.tsx  # shared multi-select restaurant state (React Context) — selectedRestaurantIds: string[]
    tests/
    package.json
  .env.example
  docs/
  CLAUDE.md
```

- Path alias: `@/` → `frontend/src/` .
- Python: snake_case for files/functions, PascalCase for classes.
- React: PascalCase component files/names, camelCase functions/variables.

## Development Commands

- `brew install postgresql@17 pgvector && brew services start postgresql@17` — one-time local Postgres + pgvector setup (macOS). Create the admin role/database matching your `.env`, then proceed with the commands below. (pgvector's Homebrew formula targets Postgres 17/18, not 16 — fine for local dev/testing, since the migration SQL itself is version-independent.)
- `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` — one-time backend environment setup. Requires Python **>=3.12** (whatever `python3` resolves to locally, as long as it satisfies that minimum).
- `cd backend && alembic upgrade head` — run migrations (needs `DATABASE_URL` reachable — a local Postgres+pgvector instance).
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
- **`menu_items.is_upsell`** (Phase 8, `NOT NULL DEFAULT false`) flags designated add-on items (e.g. "Extra Gravy," "Add Bacon") — the chosen definition of "upsell" over a heuristic like "any item beyond the first per transaction." **`transactions.campaign_id`** (Phase 8, nullable FK to `campaigns.id`, `ON DELETE SET NULL`) links a transaction to the campaign it's attributed to, populated only by the seed script — see `docs/decisions/014-campaign-attribution-mechanism.md`.
- The agent's tools connect via a **dedicated read-only Postgres role, `ask_sous_readonly`** (created in migration `0002`, see `docs/decisions/002-readonly-postgres-role.md`) — never the same credentials used by migrations/seed scripts. This is a hard boundary, not a convention to relax under time pressure. Proven by integration test (`backend/tests/integration/test_db_bootstrap.py`), not just asserted. **Concretely, `app/agent/tools/db.py` is the only module in `app/agent/` permitted to open a database connection** (`readonly_connection()`) — every tool function goes through it, and nothing in `app/agent/` ever imports `app/db/session.py`'s admin-credentialed path. A fresh engine is created and disposed per call, not cached — see `docs/decisions/005-readonly-tool-connection-lifecycle.md` for why (asyncpg connections are bound to their creating event loop; Phase 0 already hit and reverted a module-scoped-engine bug for the same reason).
- The seed script (`app/seed/seed.py`/`generators.py`) generates deterministic primary-key UUIDs drawn from its seeded RNG (`uuid.UUID(int=rng.getrandbits(128), version=4)`), not `uuid.uuid4()`, so re-seeding is byte-for-byte reproducible. **This convention is scoped to `seed.py`/`generators.py` only** — Phase 7's live-trickle generator (`trickle.py`) uses genuine `uuid.uuid4()`/`random` module randomness and must not reuse the fixed seed, since it exists specifically to simulate non-deterministic ongoing activity. See `docs/decisions/004-seed-data-determinism-and-patterns.md` and `docs/decisions/012-live-trickle-generator.md`.
- **Live-trickle generator (Phase 7):** `run_trickle_loop()` (`app/seed/trickle.py`) is started as a background `asyncio.Task` from `main.py`'s `lifespan` context manager only when `ENABLE_TRICKLE=true` (default `false`), cancelled cleanly on shutdown. No manual on-demand trigger endpoint exists — this is deliberate, per implementation-plan.md 7.1. Writes go through the same privileged `async_session_maker` `seed.py` uses, not `readonly_connection()` — the agent's read-only DB boundary applies to `app/agent/` tool code, not the whole app.

### Agent / grounding
- Every agent turn logs: the question, every tool call (with arguments), each tool's raw result, which model handled the turn, and the final answer (via `structlog`). Concretely (Phase 3): `agent_turn_started`, `tool_call_requested`, `tool_call_result`, `agent_turn_model_selected`, `agent_turn_completed`, all correlated by a per-turn `turn_id` bound via `structlog.contextvars.bind_contextvars()` and cleared in a `finally` block — see `backend/app/agent/insights.py`.
- **No naked numbers rule:** the agent must never state a number without a corresponding logged tool call backing it, for that turn. Enforce this in code review. Backed (Phase 3) by a best-effort, non-blocking `_check_grounding()` check that logs a `possible_ungrounded_numeric_answer` warning when an answer contains a digit but no tool was called that turn, plus a test-level guard (`tests/integration/test_grounding_guard.py`) proving the test suite itself would catch a genuinely ungrounded response for data-requiring questions.
- Aggregation tools (Phase 2) and the raw SQL tool (Phase 3, `run_readonly_query()`) both execute parameterised queries only — no dynamic table/column names built from LLM output. The one place a tool selects a SQL fragment by argument value (`cohort_comparison.py`'s `metric` parameter) does so via a small hardcoded allow-list dict with a runtime `ValueError` guard for anything outside it — never via f-string/`.format()` on caller input. Follow this pattern for any future tool that needs the same kind of "pick one of a few fixed expressions" behaviour. The raw SQL tool additionally validates its (partly LLM-authored) query text structurally via `sqlglot` before it ever reaches Postgres — see `docs/decisions/006-raw-sql-tool-safety-mechanism.md`.
- **Pure/impure split** — every `app/agent/tools/` module separates a pure computation function (`_summarize_daily_rows`, `_build_item_velocities`, `_prior_period`/`_compare`, `_ratio`, `_validate_select_only`/`_enforce_row_cap`, `_build_upsell_metrics`, `_build_campaign_performance`) that takes plain data and returns a dataclass, no DB/event loop involved, from a thin `async def get_x()` wrapper that fetches rows and delegates to it. Established in Phase 1 (`generators.py`/`seed.py`) and carried forward in every phase since — keep following it for any future tool, since it's what makes the fast, DB-free unit-test layer possible at all.
- **`app/agent/llm_client.py` and `app/agent/embedding_client.py` are the only modules in `app/agent/` or `app/api/` permitted to import `google.genai`.** `GeminiClient` accepts and returns only this app's own frozen dataclasses (`ToolDeclaration`, `UserText`/`ModelToolCalls`/`ToolResultsTurn`, `ToolCallRequest`/`FinalAnswer`); `EmbeddingClient.embed_texts()` accepts `list[str]` and returns `list[list[float]]` — neither ever exposes a raw SDK type — so every layer above them (`tool_registry.py`, `insights.py`, `chat.py`, `vector_search.py`, `embed_seed_data.py`) is testable with plain `AsyncMock` and zero GCP dependency. Verify with `grep -rn "from google" app/agent/ app/api/` — it should show hits only in `llm_client.py` and `embedding_client.py`. Both adapters catch `google.auth.exceptions.GoogleAuthError` alongside SDK-level errors when translating to `AgentUnavailableError` — a missing/invalid credentials failure (this environment's current default state) needs the same translation as a rate limit or outage. See `docs/decisions/007-gemini-model-selection-and-client-adapter.md` and `docs/decisions/008-embedding-model-and-client-adapter.md`.
- **Eleven LLM-callable tools** (`INSIGHTS_TOOLS`/`TOOL_DISPATCH` in `tool_registry.py`): the four Phase 2 aggregation tools, `run_readonly_query` (Phase 3), `search_customer_reviews` (Phase 4, pgvector similarity search over `reviews.embedding` — see `docs/decisions/009-vector-retrieval-tool-design.md`), four Phase 8 tools — `compare_locations`/`get_upsell_metrics` (multi-restaurant, take `restaurant_ids: list[uuid.UUID]`) and `list_campaigns`/`get_campaign_performance` (single-restaurant/single-campaign) — and `get_weekday_performance` (groups revenue by day-of-week; shared by both chat and campaign generation so the two never disagree on the same fact — see `docs/decisions/016-agentic-campaign-generation.md`). Qualitative questions about customer sentiment must go through `search_customer_reviews`, never invented/paraphrased review content — enforced via the system instruction in `app/agent/prompts/insights_system_instruction.py`, same "no naked numbers"-style discipline applied to qualitative claims. `search_similar_campaigns` (also in `vector_search.py`) is built but deliberately **not** registered as an LLM-callable tool — it's a plain function for Phase 5's campaign generation to call directly, not something the model decides to invoke mid-conversation.
- **Multi-restaurant chat (Phase 8):** `answer_question()`/`answer_question_stream()`/`build_insights_system_instruction()` all take `restaurant_ids: list[uuid.UUID]`, not a singular `restaurant_id` — a list of one is the single-restaurant case, not a separate code path. The system instruction switches between single- and multi-restaurant guidance text based on selection count, directing the model to `compare_locations`/`get_upsell_metrics` (not a loop of single-restaurant tool calls) when more than one restaurant is selected. See `docs/decisions/015-multi-restaurant-chat-design.md` for the full rationale, including the deliberate tool-surface asymmetry (only `compare_locations`/`get_upsell_metrics` are list-first; `get_revenue_summary`/`get_item_velocity`/etc. remain single-restaurant) and why `/campaigns` was deliberately excluded from this pattern.
- **Access point (Phase 6 — breaking change from the standard envelope; Phase 8 — breaking change again for `restaurant_ids`):** `POST /chat` (`backend/app/api/chat.py`) — request `{restaurant_ids: [...], question}` (was singular `restaurant_id` through Phase 7), response is a **Server-Sent-Events stream** (`text/event-stream`), not the standard `{data, error}` JSON envelope every other endpoint uses. Each event is `data: {...}\n\n` with a `type` discriminator: `text_chunk` (`{text}`), `done` (the old `{answer, tool_calls, model}` shape), or `error` (`{message, code}`, sent for a failure that happens *after* streaming has already started — a failure *before* the first chunk still returns a normal 503/502 JSON response through the usual exception handlers). Calls `answer_question_stream()`, not `answer_question()`. See `docs/decisions/011-sse-streaming-and-mid-stream-errors.md` for the SSE rationale and `docs/decisions/015-multi-restaurant-chat-design.md` for the `restaurant_ids` rationale, including why `curl -d ...` against this endpoint now returns raw SSE frames instead of one JSON body. Checks every restaurant's existence via the shared `restaurant_exists()` helper (`app/agent/tools/restaurant_lookup.py`, fanned out via `asyncio.gather`) first, as a normal JSON 404 (no SSE stream opened just to error); never imports `llm_client` directly.
- **`GET /restaurants`** (`backend/app/api/restaurants.py`) — no request body, response `{restaurants: [{id, name}]}` inside the standard envelope, sorted by name. Backs the frontend's restaurant switcher. Uses the shared `list_restaurants()` in `restaurant_lookup.py`.
- **`GET /dashboard?restaurant_ids=...`** (Phase 7, Phase 8 — `backend/app/api/dashboard.py`) — `restaurant_ids` is a repeated query param (was singular `restaurant_id` through Phase 7); response is always `{locations: [{restaurant_id, restaurant_name, kpis, revenue_trend, upsell_attach_rate}, ...], totals, top_items}` — one shape regardless of selection count. `top_items` is populated (via `get_item_velocity()`, re-sorted by `total_quantity` descending) only when exactly one restaurant is selected — `get_item_velocity()` has no multi-restaurant form (see `docs/decisions/015-multi-restaurant-chat-design.md`'s Consequences for why this is a known, accepted asymmetry rather than a bug). `locations`/`upsell_attach_rate`/`totals` reuse `compare_locations()`/`get_upsell_metrics()` (fanned out concurrently via `asyncio.gather`, alongside `list_restaurants()` which also serves as the existence check — no separate `restaurant_exists()` round trip). Not an agent path at all: never touches `tool_registry.py`/`insights.py`. KPI/revenue/rate values are exact Decimal strings; the frontend formats them at render time (`DashboardPage.tsx`'s `formatCurrency()`/`formatPercent()`), not the backend. Frontend: a single selected location renders the original KPI-row-plus-charts layout unchanged; 2+ selected locations render a combined comparison table with per-location revenue sparklines and an upsell-rate column instead.
- **Model routing (Phase 5):** insights Q&A defaults to `FLASH_MODEL`, escalating to `PRO_MODEL` per-round via `_select_model()` in `insights.py` — either immediately, if the question matches a "deeper analysis" keyword (`"deep dive"`, `"thorough"`, etc.), or once a turn has already needed `ESCALATION_TOOL_CALL_THRESHOLD` (3) rounds without reaching a final answer. Campaign generation (`app/agent/campaigns.py`) always uses `PRO_MODEL` unconditionally — no routing decision there. Every routing choice is logged on `agent_turn_model_selected` with a `routing_reason` (`"default"` / `"tool_call_threshold"` / `"keyword"`). See `docs/decisions/010-model-routing-heuristic.md`.
- **Campaign generation (Phase 5, agentic since ADR-016):** `POST /campaigns` (`backend/app/api/campaigns.py`) — request `{restaurant_id, brief}` (deliberately stays singular — see below), response `{copy_text, examples_used, model, tool_calls}`. `generate_campaign()` fetches `restaurants.brand_voice_guide` via `get_brand_voice_guide()` and retrieves up to `CAMPAIGN_EXAMPLE_TOP_K` (2) similar past campaigns via `search_similar_campaigns()` as a fixed pre-fetch (every brief needs both, so this isn't a model decision), builds the system instruction (`build_campaign_system_instruction()`, now also given the restaurant's id and today's date so the model can construct valid tool arguments), then runs the same bounded tool-calling loop `answer_question()` uses — offered the full `INSIGHTS_TOOLS` roster, up to `MAX_TOOL_CALL_ROUNDS` on `PRO_MODEL`, reusing `insights.py`'s `_resolve_tool_call_round()`/`_check_grounding()` rather than reimplementing them — so a brief referencing a specific fact ("our slowest weekday") gets looked up instead of invented, while a tone-only brief resolves in one round with zero tool calls. Raises `AgentIncompleteError` if the round cap is hit, same as insights Q&A. Proceeds normally (not an error) when zero past campaigns are found. Logs `campaign_turn_started`/`campaign_examples_retrieved`/`campaign_turn_completed`, same per-turn `turn_id`-correlated audit pattern as `answer_question()`. Does not persist generated copy back to the `campaigns` table — copy is returned to the caller only, not auto-saved. Tool calls made during generation are returned on `tool_calls` and rendered in `CampaignsPanel.tsx` as citation chips, reusing the same `CitationChip` component chat uses. **Deliberately excluded from Phase 8's `restaurant_ids` pattern** — brand voice/copy generation only makes sense for one restaurant at a time; the frontend always scopes to the first selected restaurant and disables Generate (with an explanatory `StatusTag`) when more than one is selected, rather than the backend silently picking one. See `docs/decisions/015-multi-restaurant-chat-design.md` and `docs/decisions/016-agentic-campaign-generation.md`.
- **Campaign attribution and upsell measurement (Phase 8):** `transactions.campaign_id` (nullable FK, `ON DELETE SET NULL`) and `menu_items.is_upsell` (boolean) are both populated only by the seed script — `app/seed/generators.py`'s `attribute_transactions_to_campaigns()` probabilistically attributes a subset of transactions in a fixed post-`sent_at` window to each sent campaign (first-touch, non-overlapping), and upsell/add-on menu items are tagged and probabilistically attached during transaction generation. Neither is writable from any live API path. See `docs/decisions/014-campaign-attribution-mechanism.md` for the full mechanism and its limitations.

### State management (frontend)
- Server state: TanStack Query (e.g. `App.tsx`'s `useQuery(["restaurants"], getRestaurants)`).
- Client/UI-only state (selected restaurants, panel toggles): React Context or local `useState` — no need for a separate state library at this scale. Concretely (Phase 6, multi-select since Phase 8): `RestaurantProvider`/`useRestaurantContext()` (`lib/restaurant-context.tsx`) holds `selectedRestaurantIds: string[]` — always at least one, defaulting to just the first restaurant (matching the original single-selection behavior); `toggleRestaurant(id)` refuses to remove the last remaining selection rather than allowing an empty set. `ChatPage`/`DashboardPage` are mounted with `key={selectedRestaurantIds.join(",")}` and `CampaignsPanel` with `key={primaryRestaurantId}` in `App.tsx` so any selection change remounts them and resets their per-restaurant local state (chat history, campaign draft) — a real bug caught during manual verification in Phase 6, not a defensive guess.
- `RestaurantSwitcher.tsx` is a checkbox-based multi-select dropdown built from plain elements (a trigger button + an outside-click-dismissed panel), not a headless dropdown-menu primitive (design-guidelines.md §8's general pattern) — a deliberate simplification carried forward from the original Phase 6 native-`<select>` reasoning: this is purely a data-context switch (design-guidelines.md §5) rather than a case where a richer visual treatment carries real product value. Trigger label shows the single restaurant's name when exactly one is selected, or "N locations selected" otherwise; a "Select all" checkbox selects every restaurant at once.
- `CampaignsPanel` receives only the first selected restaurant id (`isMultipleSelected` prop signals when more than one is selected) — see the `/campaigns` note above.

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
