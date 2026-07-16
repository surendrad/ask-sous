# Ask Sous — Implementation Plan

**Version:** 1.0
**Date:** 2026-07-15
**Status:** Draft
**Source documents:** master-plan.md, stack.md

---

## Overview

Ask Sous is built backend-first, matching the requirements doc's own build order: get the agent answering real questions correctly against raw SQL and pre-built tools, verified by hand, before any UI exists. Each phase after Foundation ends in something concretely testable — a query result, a CLI/API response, a logged agent turn — so grounding correctness (the project's core success metric) can be checked at every step rather than discovered late, after a UI is layered on top.

The **MVP is Phases 0–6**: foundation through a working frontend covering both insights Q&A and campaign generation. Phase 7 (live-trickle generator, dashboard charts) is explicitly nice-to-have polish per the master plan and isn't required to demo the core story.

### Phase Summary

| Phase | Name | Description | Depends on |
|-------|------|-------------|------------|
| 0 | Project Foundation | Repo structure, tooling, Docker Compose, GCP/Vertex AI setup, DB schema skeleton, app shell | — |
| 1 | Data Layer | Full schema, migrations, Faker seed script with deliberate verifiable patterns | 0 |
| 2 | Aggregation Tools | Pre-built read-only aggregation functions, tested directly against seed patterns | 1 |
| 3 | Agent Core (Insights Q&A) | Vertex AI integration, function-calling, raw SQL tool, turn logging, CLI/API-level Q&A | 2 |
| 4 | Vector Retrieval | pgvector embeddings for reviews/campaigns, similarity search tool | 1, 3 |
| 5 | Campaign Generation | Campaign tool/prompt path, brand-voice + few-shot retrieval, model routing to Pro-tier | 3, 4 |
| 6 | Frontend | Chat UI (streaming), restaurant switcher, campaigns panel, applied design system | 3, 5, `/designer` |
| 7 | Polish (post-MVP) | Live-trickle background generator, dashboard charts | 6 |

---

## Phase 0: Project Foundation

**Status:** ✅ Complete (2026-07-15). Plan: `docs/plans/phase-0-project-foundation.md`. See `docs/changelog.md` for what shipped and the deviations discovered during implementation (readonly-role password binding, CORS, Docker unavailable in the implementation environment).

**Goal:** A running local environment — empty of features, but with every piece of infrastructure, tooling, and scaffolding in place — so every later phase is pure feature work.

### 0.1 Repository & tooling
- Monorepo layout: `backend/` (Python/FastAPI) and `frontend/` (React/Vite), per Project Structure conventions below.
- `pyproject.toml` with Ruff configured; `package.json` with Biome configured.
- `pre-commit` configured to run Ruff (backend) and Biome (frontend) on staged files.
- Conventional Commits documented in `CONTRIBUTING.md` or a note in `README.md`.

### 0.2 Environment & secrets
- `.env.example` at repo root covering: `DATABASE_URL`, `GOOGLE_APPLICATION_CREDENTIALS` (path to service account key), `GCP_PROJECT_ID`, `GCP_REGION`, `ENABLE_TRICKLE` (bool, default false).
- `.env` and any service account key files added to `.gitignore`.
- **Manual prerequisite (user action, not Claude):** create a GCP project, enable the Vertex AI API, enable billing, create a service account with Vertex AI User role, download its key. Document these exact steps in `docs/deployment/first-time-setup.md` — or, since this is local-only, as a short `docs/reference/gcp-setup.md` — so it's a one-time checklist rather than tribal knowledge.

### 0.3 Database
- `docker-compose.yml` with a Postgres service using a `pgvector`-enabled image (e.g. `pgvector/pgvector:pg16`) and the FastAPI backend service.
- Alembic initialised in `backend/app/db/migrations/`.
- First migration: enable the `vector` extension (schema-only — tables come in Phase 1).
- Dedicated read-only Postgres role created via migration or init script, ready for Phase 2 onward.

### 0.4 Backend shell
- FastAPI app with a `GET /health` endpoint returning `{ "status": "ok" }` — the phase's visible increment.
- `structlog` configured for JSON logging.
- Consistent error response shape (`{ "error": { "message", "code" } }`) wired into a global exception handler, even though nothing throws real errors yet.

### 0.5 Frontend shell
- Vite + React + TypeScript scaffold, Tailwind CSS + shadcn/ui installed.
- Design tokens from `docs/definition/design-guidelines.md` applied to the Tailwind config (this phase runs after `/designer`, so tokens will exist by the time this is built).
- A single placeholder page confirming the shell renders and can reach the backend `/health` endpoint — the phase's visible frontend increment.

### Testing
- A smoke test hitting `/health` and asserting `200 { status: ok }`.
- A config-loading test confirming required env vars are validated at startup (fails fast if `DATABASE_URL` or GCP vars are missing).

---

## Phase 1: Data Layer

**Status:** ✅ Complete (2026-07-15). Plan: `docs/plans/phase-1-data-layer.md`. Ground truth reference: `docs/reference/seed-patterns.md`. See `docs/changelog.md` for what shipped.

**Goal:** A fully seeded database with realistic, deliberately-patterned data that can be independently verified by direct query.

### 1.1 Schema
- SQLAlchemy models for `restaurants`, `menu_items`, `transactions`, `transaction_items`, `reviews`, `campaigns` (see stack.md / master-plan.md §3 for fields).
- UUID primary keys, `created_at`/`updated_at` timestamps on all tables.
- Alembic migration for the full schema, including `vector` columns on `reviews.embedding` and `campaigns.embedding` (populated in Phase 4 — columns exist now, values come later).

### 1.2 Seed script
- `seed.py`: Faker-based generator, **fixed random seed** for full determinism across runs.
- Minimum 5 restaurants, 90 days of transaction history each, varied by day-of-week/time-of-day.
- Deliberate, documented patterns baked in (e.g. Restaurant A genuinely slower on Tuesdays, Restaurant B has one item genuinely trending up over the 90 days) — write these patterns down in a comment or a small `docs/reference/seed-patterns.md` so they're easy to check against later.
- Idempotent: re-running `seed.py` truncates and regenerates cleanly, same output every time (deterministic seed).

### Testing
- Unit tests on the data generators: e.g. "Restaurant A's Tuesday revenue is below its weekly average across the generated range."
- Integration test: run the seed script against a test database, assert row counts and that key patterns are present via direct query.

---

## Phase 2: Aggregation Tools

**Status:** ✅ Complete (2026-07-15). Plan: `docs/plans/phase-2-aggregation-tools.md`. See `docs/changelog.md` for what shipped.

**Goal:** The pre-built aggregation functions that answer the 80% case, proven correct against Phase 1's known data patterns — independent of any LLM.

### 2.1 Tools
- Revenue summary (by restaurant, date range).
- Item velocity (trending up/down over a window).
- Day-over-day / week-over-week comparison.
- Peer/cohort comparison across restaurants.
- Implemented as plain Python functions using parameterised SQL (`text()` or `asyncpg`), executed via the dedicated **read-only** Postgres role from Phase 0.3.

### 2.2 Correctness
- Because this is the project's core success metric, this phase gets deliberately thorough testing (heavier than the project's general "practical" testing depth) — each aggregation function is tested against the exact patterns seeded in Phase 1, with hand-computable expected values.

### Testing
- Unit tests per aggregation function against fixture data with known expected output.
- Integration tests against the full seeded database, asserting each function surfaces the patterns deliberately baked into Phase 1 (e.g. the trending item is actually detected as trending).

---

## Phase 3: Agent Core (Insights Q&A)

**Status:** ✅ Buildable and tested (2026-07-16). Plan: `docs/plans/phase-3-agent-core.md`. See `docs/changelog.md` for what shipped. **Live-credentials gap:** everything is built and verified against fixture/mocked Vertex AI responses — no live GCP credentials exist in this environment (`.env` still has placeholder values; `docs/reference/gcp-setup.md`'s checklist hasn't been run). UAT-3.1 through UAT-3.4 are completable now; UAT-3.5 and UAT-3.6 explicitly require live Vertex AI credentials and remain unverified until then.

**Goal:** A working, gradeable agent that answers real questions via tool calls — testable from a terminal, no UI required yet.

### 3.1 Agent setup
- Vertex AI SDK (`google-genai`) client configured for Gemini Flash 2.5.
- Tool/function-calling definitions wrapping every Phase 2 aggregation function, plus a raw parameterised **read-only** SQL tool for anything not pre-aggregated.
- A Python function assembling tool call results into the final grounded prompt/response.

### 3.2 Grounding & audit logging
- Every agent turn logs: the user's question, every tool call made (with arguments), each tool's raw result, which model handled the turn, and the final answer — via `structlog`.
- Convention (enforced in code review during `/implement`): the agent must never state a number that isn't backed by a logged tool call result for that turn.

### 3.3 Access point
- A `/chat` API endpoint (or a CLI script, whichever is faster to stand up first) so insights Q&A can be exercised end-to-end without a frontend.
- Manually verify: ask each of a fixed set of test questions per restaurant, cross-check the answer against Phase 1's known seed patterns by hand.

### Testing
- Integration tests using recorded/fixture Gemini responses (to keep tests fast and free) verifying tool-call assembly and logging.
- A guard test confirming no response reaches the client without at least one corresponding logged tool call, for questions that require data.

---

## Phase 4: Vector Retrieval

**Status:** ✅ Buildable and tested (2026-07-16). Plan: `docs/plans/phase-4-vector-retrieval.md`. See `docs/changelog.md` for what shipped. **Live-credentials gap** (same caveat as Phase 3): everything is built and verified via fixture/mocked Vertex AI responses and hand-crafted vectors inserted directly into real seeded rows — no live GCP credentials exist in this environment. UAT-4.1 through UAT-4.3 are completable now; UAT-4.4 and UAT-4.5 explicitly require live Vertex AI credentials and remain unverified until then.

**Goal:** Qualitative grounding — reviews and past campaign copy become searchable context for both Q&A and campaign generation.

### 4.1 Embeddings
- Vertex AI embedding model generates vectors for `reviews.review_text` and `campaigns.copy_text`.
- Embedding generation runs as an extension of the seed process (or a follow-up script), deterministic given the fixed seed data.

### 4.2 Retrieval tool
- A pgvector similarity search tool added to the agent's toolset, usable for qualitative Q&A ("what are customers saying about X?") and for campaign few-shot retrieval (Phase 5).

### Testing
- Unit test for the embedding generation function (correct dimensionality, deterministic output for identical input).
- Integration test: similarity search against fixture reviews returns the expected nearest neighbours for a known query.

---

## Phase 5: Campaign Generation

**Status:** ✅ Buildable and tested (2026-07-16). Plan: `docs/plans/phase-5-campaign-generation.md`. See `docs/changelog.md` for what shipped. **Live-credentials gap** (same caveat as Phases 3–4): everything is built and verified against fixture/mocked Vertex AI responses and hand-crafted vectors. UAT-5.1 through UAT-5.4 are completable now; UAT-5.5 and UAT-5.6 explicitly require live Vertex AI credentials and remain unverified until then.

**Goal:** Grounded campaign copy, with model routing demonstrating the fast/cheap-default-escalate-when-it-matters pattern.

### 5.1 Campaign tool/prompt path
- For a campaign request, retrieve the restaurant's brand voice guide plus 1–2 past campaign examples (via the Phase 4 retrieval tool) as few-shot grounding before generating copy.

### 5.2 Model routing
- Simple, explicit heuristic: campaign requests always route to the Pro-tier model; insights questions route to Flash 2.5 by default, escalating when a query requires 3+ tool calls or the user explicitly asks for deeper analysis.
- Which model handled each turn is logged (already covered by Phase 3.2's logging — this phase just adds the routing decision itself as a logged field).

### Testing
- Unit test the routing heuristic directly: given a set of example inputs (campaign request, simple insights question, complex multi-tool-call question), assert the correct model is selected.
- Integration test for the full campaign generation flow end-to-end via the Phase 3 access point.

---

## Phase 6: Frontend (MVP completion)

**Status:** ✅ Buildable and tested (2026-07-16). Plan: `docs/plans/phase-6-frontend.md`. See `docs/changelog.md` for what shipped. Verified against a real running backend + seeded database via Playwright MCP (not just mocks — a departure from Phases 3–5, since this phase's core work doesn't require live Vertex AI credentials to exercise meaningfully). **Live-credentials gap** (same caveat as every prior phase): the real streaming feel and a genuine mid-stream failure both remain unverified against a live model until `docs/reference/gcp-setup.md` is completed — see UAT-6.1/6.4. **Known scope trade-off:** this section's own "Playwright E2E smoke tests" requirement was descoped to a manual Playwright-MCP pass instead of committed automated tests — acknowledged explicitly in `docs/changelog.md` and `docs/uat.md`, not silently dropped.

**Goal:** The demoable product — everything built so far, wrapped in a real UI.

### 6.1 Chat interface
- Streamed responses (token-by-token) from `/chat`, rendered as they arrive.
- Shows which restaurant is currently selected.

### 6.2 Restaurant switcher
- Dropdown to switch between the 5 seeded restaurants — purely a data-context switch, no auth implications.

### 6.3 Campaigns panel
- Displays generated campaign drafts with a "regenerate" button.

### 6.4 Design system application
- Design tokens and components from `/designer`'s output applied throughout.

### Testing
- Vitest + React Testing Library component tests for the chat interface, restaurant switcher, and campaigns panel.
- Playwright E2E smoke tests introduced here (first phase with a real UI to drive): ask a question and see a grounded answer, switch restaurants, generate a campaign.

---

## Phase 7: Polish (post-MVP)

**Goal:** Optional demo polish, explicitly deferred from the MVP per the master plan.

### 7.1 Live-trickle generator
- Background asyncio task (or APScheduler job) inserting a trickle of new transactions on a timer, toggled via the `ENABLE_TRICKLE` env var (no manual on-demand trigger, per the agreed testability approach).

### 7.2 Dashboard
- 2–3 pre-computed charts (revenue trend, top items) using Recharts, for visual demo value.

### Testing
- Smoke test confirming the trickle job inserts rows over a short run when enabled, and inserts nothing when `ENABLE_TRICKLE=false`.
- Basic rendering tests for the dashboard charts.

---

## Cross-Cutting Concerns

- **Grounding & auditability:** every phase from 3 onward must maintain the "no naked numbers" rule — no agent response states a figure without a corresponding logged tool call. This is checked in code review during `/implement`, not just tested.
- **Read-only DB boundary:** the dedicated read-only Postgres role (created in Phase 0.3) is the *only* connection the agent's tools ever use, from Phase 2 onward. The app's own migrations/seed scripts use separate, privileged credentials.
- **Determinism:** the fixed random seed used in Phase 1 must also govern any embedding generation (Phase 4) — re-running the full seed + embed pipeline should be reproducible.
- **Testing depth:** Practical overall, with Phases 1 and 2 held to a higher bar since their correctness is the project's core success metric (per master-plan.md §9).
- **Logging:** `structlog` JSON logging, consistent shape, from Phase 0 onward — this is what makes the audit-trail story real, not just documented.
- **Error handling:** consistent `{ error: { message, code } }` API shape from Phase 0 onward. Vertex AI failures (rate limits, outages) are caught and surfaced as a clear "agent unavailable" error, never silently swallowed or retried indefinitely.

---

## Key Technical Decisions to Make

| Decision | Options | Needed by | Record as |
|---|---|---|---|
| Exact Vertex AI embedding model | `text-embedding-004` vs newer alternatives available at build time | Phase 4 | ADR |
| Exact Gemini Pro-tier model for escalation | Whatever Pro-tier Gemini model is current in Vertex AI at build time (the interview-prep-era model name will likely have moved on) | Phase 3 (or Phase 5 at latest) | ADR |
| Model-routing heuristic thresholds | Exact tool-call count / keyword rules for escalation | Phase 5 | ADR |
| Dataset size | 5 restaurants / 90 days (starting point) vs larger, if cohort comparisons don't feel convincing | Phase 1 | Note in seed-patterns doc, revisit if needed |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Vertex AI cost/quota surprises during development | Medium | Low | Flash 2.5 default keeps cost low; monitor GCP billing dashboard; use free-tier credits if available |
| Reference Gemini Pro-tier model has been deprecated/renamed since interview prep | Medium | Medium | Confirm current model availability at the start of Phase 3, not assumed in advance |
| Seed data patterns aren't obviously verifiable by hand | High (undermines the core success metric) | Low | Explicit pattern-verification tests in Phase 1; document expected patterns in `seed-patterns.md` |
| pgvector setup/performance issues in local Docker | Low | Low | Use the official `pgvector/pgvector` Docker image rather than adding the extension manually |
| Streaming responses complicate audit logging | Medium | Medium | Log the full assembled response server-side after the stream completes, not just what's sent to the client |

---

## MVP Definition

**MVP = Phases 0 through 6.** This covers: full data layer, aggregation tools, a working grounded insights agent, vector retrieval, campaign generation with model routing, and a real frontend — everything needed to demo both v1 goals (grounded Q&A and grounded campaign generation) end-to-end.

**Phase 7 (live-trickle generator, dashboard charts) is explicit post-MVP polish**, matching the master plan's own "nice-to-have" framing — valuable for a richer demo, but not required to prove the core concept.
