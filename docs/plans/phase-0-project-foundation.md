# Phase 0: Project Foundation — Implementation Plan

**Date:** 2026-07-15
**Status:** In Progress
**Source:** implementation-plan.md Phase 0

---

## Goal

Stand up every piece of infrastructure, tooling, and scaffolding Ask Sous needs — monorepo layout, linting/formatting, Docker Compose, a Postgres+pgvector database with its migration framework and the dedicated read-only role, a FastAPI backend shell with logging and error handling, and a React/Vite/Tailwind/shadcn frontend shell wired to the design system — so that every phase from here on (1 through 7) is pure feature work against a stable, already-decided foundation. Nothing in this phase is user-facing product functionality; its "feature" is a `GET /health` round-trip from the browser to the database's presence, proving every layer is wired together correctly. This matters disproportionately for Ask Sous specifically because the project's whole point is being able to defend *why* each piece was built the way it was in an interview — so the read-only DB boundary, the response envelope, and the design-token wiring all need to be right and defensible from the first commit-equivalent forward, not patched in later.

## Prerequisites

- Docker Desktop (or equivalent Docker Engine + Compose v2) installed and running locally.
- Node.js 20+ and npm installed locally (for the Vite/frontend tooling and shadcn/Biome CLIs).
- Python 3.12 installed locally, with the ability to create a virtualenv (`python3.12 -m venv`) — the backend is run locally against the Dockerised Postgres, not exclusively inside its own container, so `alembic` and `pytest` can be run directly per `CLAUDE.md`'s Development Commands.
- No prior phases — this is Phase 0, the first.
- A GCP account/project is **not** required to complete this phase (no live Vertex AI calls are made until Phase 3). `docs/reference/gcp-setup.md`, written in this phase, documents the one-time manual checklist so it can be done ahead of Phase 3 whenever convenient.
- Per explicit user instruction for this session: **git is not being initialized.** This plan creates all files (including `.gitignore` and `.pre-commit-config.yaml`) so the repository is ready for `git init` whenever that happens, but includes no `git init`, `git add`, `git commit`, or `pre-commit install` actions. Manual verification steps substitute direct tool invocation (`ruff`, `biome`) for what `pre-commit run --all-files` would otherwise check, since that command requires a `.git` directory.

## Implementation Details

### 0.1 Repository & tooling

Establish the monorepo skeleton described in `CLAUDE.md`'s Project Structure section, plus the linting/formatting toolchain. This is scaffolding/config work — per `CLAUDE.md`'s TDD exceptions ("UI layout, config, and scaffolding"), no red-green cycle applies here; correctness is checked via direct tool invocation in Testing, below.

- Create the top-level layout: `backend/`, `frontend/`, plus the docs directories that already exist.
- Under `backend/app/`, create empty packages (each with a minimal `__init__.py`, one-line docstring noting which phase populates it) for: `api/`, `agent/`, `agent/tools/`, `agent/prompts/`, `db/`, `seed/`, `core/`. This isn't premature feature-building — it's fixing the directory contract now (per `CLAUDE.md`'s Project Structure) so Phases 1–5 never need to restructure imports, only add files.
- Create `backend/pyproject.toml`: PEP 621 project metadata (name `ask-sous-backend`, `requires-python = ">=3.12"`), Phase-0-only runtime dependencies (`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `structlog`), dev dependencies (`pytest`, `pytest-asyncio`, `httpx`, `ruff`) under an optional `[project.optional-dependencies] dev`. Deliberately excludes `google-genai`, `Faker`, `Recharts`-equivalents, etc. — those are added by the phase that first needs them (Phase 3, Phase 1, Phase 7 respectively), keeping `pyproject.toml` an honest record of what's actually used.
- Add `[tool.ruff]` to `pyproject.toml`: `target-version = "py312"`, `line-length = 100`, `select` covering at least `E, F, I, W, UP, B`, and `[tool.ruff.format]` enabled (Ruff as the single lint+format tool, per `stack.md`).
- Scaffold the frontend with `npm create vite@latest frontend -- --template react-ts`, then remove Vite's default boilerplate (`App.css` demo styles, default SVG assets) since they'll be replaced by the design system in 0.5.
- Install `@biomejs/biome` as a frontend dev dependency; create `frontend/biome.json` enabling the linter and formatter, with `dist/`, `node_modules/`, and `coverage/` ignored, and import-sorting enabled.
- Create root `.pre-commit-config.yaml` configuring: a Ruff hook (via the `ruff-pre-commit` repo, `ruff check --fix` + `ruff format`, scoped to `backend/`) and a local hook running `npx biome check --write` scoped to `frontend/` staged files. **Do not run `pre-commit install`** — there's no `.git` directory yet for it to hook into. Add a comment at the top of the file noting `pre-commit install` should be run once `git init` happens.
- Add a short section to root `README.md` documenting that this project uses **Conventional Commits** for commit messages once version control is initialized (`feat:`, `fix:`, `chore:`, `docs:`, etc.) — pure documentation, no git action performed.

**Tasks:**
- [ ] Create the monorepo directory skeleton (`backend/app/{api,agent,agent/tools,agent/prompts,db,seed,core}` with `__init__.py` stubs)
- [ ] Create `backend/pyproject.toml` with Phase-0 dependencies and `[tool.ruff]` config
- [ ] Scaffold `frontend/` via Vite React-TS template and remove default boilerplate
- [ ] Install Biome and create `frontend/biome.json`
- [ ] Create root `.pre-commit-config.yaml` (Ruff + Biome hooks, not installed this session)
- [ ] Add a Conventional Commits note to `README.md`
- [ ] Refactor: confirm `backend/app/__init__.py` files don't accidentally shadow stdlib module names, and that `frontend/` builds cleanly with `npm run build` after removing Vite boilerplate

### 0.2 Environment & secrets

Set up the `.env` contract and the one-time manual GCP checklist. Also pure config/docs — no tests, verified manually.

- Create root `.env.example` with every variable the app needs so far, grouped and commented:
  - `DATABASE_URL` — admin/migration Postgres connection string (e.g. `postgresql+asyncpg://ask_sous:changeme@localhost:5432/ask_sous`).
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — consumed directly by `docker-compose.yml` to initialise the Postgres container; comment noting these **must stay consistent with `DATABASE_URL`** above.
  - `READONLY_DB_PASSWORD` — password for the dedicated read-only role (`ask_sous_readonly`) created in 0.3; consumed by the Phase 0 migration now, and by the agent's tool connections from Phase 2 onward. Added now, beyond the four variables implementation-plan.md names explicitly, because the read-only role is created in this phase and its password must not be hardcoded into a migration file.
  - `GOOGLE_APPLICATION_CREDENTIALS` — local filesystem path to the downloaded GCP service account JSON key.
  - `GCP_PROJECT_ID`, `GCP_REGION`.
  - `ENABLE_TRICKLE` — bool, default `false` (unused until Phase 7, present now so the env contract is stable).
- Create root `.gitignore` (the file exists and is correct now, ready for whenever `git init` happens): `.env`, `.env.*.local`, `*service-account*.json`, `*credentials*.json`, `*.key.json`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `dist/`, `build/`, `.pytest_cache/`, `.ruff_cache/`, `coverage/`, `.DS_Store`.
- Create `frontend/.env.example` with `VITE_API_BASE_URL=http://localhost:8000` — kept separate from the root `.env.example` because Vite env vars are bundled client-side and must never carry backend secrets.
- Write `docs/reference/gcp-setup.md`: a one-time manual checklist (explicitly **not** automated by Claude) covering: create or select a GCP project; enable billing; enable the Vertex AI API (`aiplatform.googleapis.com`); create a service account with the `Vertex AI User` (`roles/aiplatform.user`) role; create and download its JSON key; store the key file **outside the repo tree or in a path already covered by `.gitignore`**; set `GOOGLE_APPLICATION_CREDENTIALS` to that path in the local `.env`; set `GCP_PROJECT_ID`; choose a `GCP_REGION` with Gemini model availability (e.g. `us-central1`) and a note to re-confirm current model/region availability at the start of Phase 3, since availability shifts over time (per the implementation plan's risk register); a reminder to check free-tier credit / billing alerts before heavy use.

**Tasks:**
- [ ] Create root `.env.example` with all Phase-0 variables and inline comments
- [ ] Create root `.gitignore` covering secrets, key files, and standard build/cache artefacts
- [ ] Create `frontend/.env.example` with `VITE_API_BASE_URL`
- [ ] Write `docs/reference/gcp-setup.md` as a manual, one-time checklist

### 0.3 Database

Bring up Postgres with pgvector via Docker Compose, initialise Alembic, and create the schema-less "vector extension only" migration plus the dedicated read-only role — the hard security boundary called out in `CLAUDE.md`. This sub-section gets real tests because it's a security-relevant mechanism the rest of the project depends on (Phase 2 onward exclusively uses this role for agent DB access).

- Create `docker-compose.yml`:
  - `postgres` service: image `pgvector/pgvector:pg16`, env from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, named volume `pgdata:/var/lib/postgresql/data`, port `5432:5432` published, healthcheck via `pg_isready -U $POSTGRES_USER`.
  - `backend` service: `build: ./backend`, `env_file: .env`, `depends_on: { postgres: { condition: service_healthy } }`, port `8000:8000` published, volume-mounts `./backend/app:/app/app` for live reload during development, command `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- Create `backend/Dockerfile`: `python:3.12-slim` base, `WORKDIR /app`, copy `pyproject.toml`, `pip install -e ".[dev]"`, copy `app/`, `EXPOSE 8000`, default `CMD` running uvicorn (overridden by compose's command in dev).
- Create `backend/.dockerignore` (`.venv/`, `__pycache__/`, `tests/`, `.pytest_cache/`, `.ruff_cache/`).
- Initialise Alembic with the **async** template from `backend/`: `alembic init -t async app/db/migrations`. This produces `backend/alembic.ini` and `backend/app/db/migrations/{env.py, script.py.mako, versions/}`.
- Edit `backend/app/db/migrations/env.py` so it reads the connection URL from `app.core.config.get_settings().database_url` (not a hardcoded `sqlalchemy.url` in `alembic.ini`) and targets `app.db.base.Base.metadata` for autogenerate support in later phases.
- Create `backend/app/db/base.py`: `class Base(DeclarativeBase): pass` — the shared SQLAlchemy 2.0 declarative base. Phase 1's `models.py` will define tables against this same `Base`; creating it now avoids Alembic's `env.py` needing to import a `models.py` that doesn't exist yet.
- Write migration `0001_enable_vector_extension`: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`; downgrade drops it (`DROP EXTENSION IF EXISTS vector`). No tables — those are Phase 1.
- Write migration `0002_create_readonly_role`: creates the dedicated read-only Postgres role, named **`ask_sous_readonly`**. Mechanism (see ADR, below):
  1. Read `READONLY_DB_PASSWORD` from the environment inside the migration (`os.environ["READONLY_DB_PASSWORD"]`) — never hardcoded.
  2. Query `pg_roles` for an existing row with `rolname = 'ask_sous_readonly'` (Postgres has no `CREATE ROLE IF NOT EXISTS` syntax); only issue `CREATE ROLE ask_sous_readonly WITH LOGIN PASSWORD :pwd NOSUPERUSER NOCREATEDB NOCREATEROLE` (using a genuine SQLAlchemy bind parameter, not string interpolation — this works because `CREATE ROLE ... PASSWORD :pwd` is a top-level parameter position, unlike embedding a parameter inside a `DO $$ ... $$` block's string body, which would not substitute correctly) if it doesn't already exist.
  3. `GRANT CONNECT ON DATABASE <db_name> TO ask_sous_readonly;`
  4. `GRANT USAGE ON SCHEMA public TO ask_sous_readonly;`
  5. `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ask_sous_readonly;` — critically, this makes every table created *by the migration-running role* from Phase 1 onward automatically `SELECT`-able by `ask_sous_readonly` with no further per-table grants needed. This only applies to objects created by the same role that ran the `ALTER DEFAULT PRIVILEGES` statement, so it depends on Phase 1's migrations running under the same admin credentials as this one (true by construction, since both use `DATABASE_URL`).
  - Downgrade: revoke the grants and `DROP ROLE ask_sous_readonly` (acceptable for a local-only demo; no production downgrade safety needed).

**Tasks (red-green-refactor):**
- [ ] Write a failing integration test (`backend/tests/integration/test_db_bootstrap.py`) asserting the `vector` extension is present after migrations run, querying `pg_extension`
- [ ] Implement migration `0001_enable_vector_extension` to make it pass
- [ ] Write a failing integration test asserting the `ask_sous_readonly` role exists, can open a connection, and can `SELECT` from a throwaway table created by the admin connection within the test
- [ ] Write a failing integration test asserting a connection authenticated as `ask_sous_readonly` is rejected (`InsufficientPrivilege`) when attempting `CREATE TABLE`, `INSERT`, or `DROP` — this is the concrete proof of the read-only boundary
- [ ] Implement migration `0002_create_readonly_role` to make both tests pass
- [ ] Refactor: extract a shared `backend/tests/integration/conftest.py` fixture providing both an admin-credentialed and a readonly-credentialed async engine/connection, for reuse by every later phase's integration tests

### 0.4 Backend shell

Build the FastAPI app shell: fail-fast config loading, JSON structured logging, the `GET /health` endpoint in the project's exact response envelope, and a global exception handler in the matching error shape.

- Create `backend/app/core/config.py`: a `pydantic-settings` `Settings(BaseSettings)` class with required fields `database_url: str`, `google_application_credentials: str`, `gcp_project_id: str`, `gcp_region: str`, and `enable_trickle: bool = False`; `model_config = SettingsConfigDict(env_file="../.env", extra="ignore")` (path relative to `backend/`, adjusted as needed so it resolves the root `.env`). Expose a cached `get_settings()` (`functools.lru_cache`) so `Settings()` is only constructed once, and constructing it raises `pydantic.ValidationError` immediately if a required variable is missing — this is what makes startup fail fast.
- Create `backend/app/core/logging.py`: configure `structlog` with a processor chain — `structlog.contextvars.merge_contextvars`, `structlog.processors.add_log_level`, `structlog.processors.TimeStamper(fmt="iso")`, `structlog.processors.format_exc_info`, `structlog.processors.JSONRenderer()` — exposed as `configure_logging()`, called once at app startup.
- Create `backend/app/core/responses.py`: two small helpers, `success(data)` returning `{"data": data, "error": None}` and `error_response(message: str, code: str)` returning `{"data": None, "error": {"message": message, "code": code}}`. This is the **single place** the response envelope shape is defined, so every future endpoint and error handler (Phase 1 onward) reuses it rather than re-deriving the shape ad hoc.
- Create `backend/app/api/health.py`: `APIRouter()` with `GET /health` returning `success({"status": "ok"})`, i.e. exactly `{"data": {"status": "ok"}, "error": null}`.
- Create `backend/app/core/errors.py`: exception handler functions —
  - `unhandled_exception_handler(request, exc)`: logs the full exception via `structlog` (with traceback) at `error` level, but returns only a **generic** message to the client (`"An unexpected error occurred."`, code `"internal_error"`) — never the raw exception string, so internals never leak in a response body.
  - `validation_exception_handler(request, exc: RequestValidationError)`: returns `error_response(message="Invalid request.", code="validation_error")` with the underlying Pydantic error details logged server-side only, at 422.
  - Both use `error_response()` from `core/responses.py`.
- Create `backend/app/db/session.py`: `create_async_engine(settings.database_url)`, an `async_sessionmaker`, and a `get_db()` FastAPI dependency (an `async def` generator yielding a session) — not consumed by any route yet, but establishes the exact pattern Phase 1's routes will use.
- Create `backend/app/main.py`: instantiate `FastAPI()`, call `configure_logging()` at startup, `include_router(health.router)`, register both exception handlers via `app.add_exception_handler(...)`.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_config.py`) for: `Settings()` raising `ValidationError` when `DATABASE_URL` is unset; raising when any GCP var is unset; loading successfully with all required vars present; `enable_trickle` defaulting to `False` when unset
- [ ] Implement `backend/app/core/config.py` to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_health.py`, using `httpx.AsyncClient` with `ASGITransport`) asserting `GET /health` returns status 200 and body exactly `{"data": {"status": "ok"}, "error": null}`
- [ ] Implement `backend/app/api/health.py`, `backend/app/core/responses.py`, and wire the router into `main.py` to make it pass
- [ ] Write failing unit tests (`backend/tests/unit/test_error_handlers.py`) asserting `unhandled_exception_handler` returns `{"data": null, "error": {"message": "An unexpected error occurred.", "code": "internal_error"}}` at 500 for an arbitrary exception, and `validation_exception_handler` returns the `validation_error` shape at 422 — call the handler functions directly with a constructed `Request` and exception instance
- [ ] Implement `backend/app/core/errors.py` and register both handlers in `main.py` to make these pass
- [ ] Create `backend/app/core/logging.py` and call `configure_logging()` from `main.py` (scaffolding — no dedicated test; verified by inspecting log output format in Manual Verification)
- [ ] Create `backend/app/db/session.py` with the async engine, sessionmaker, and `get_db()` dependency (scaffolding — no route consumes it yet, so no test; Phase 1 will test it via real queries)
- [ ] Refactor: confirm `health.py` and `errors.py` both import `success`/`error_response` from `core/responses.py` rather than constructing the envelope dict inline anywhere

### 0.5 Frontend shell

Vite + React + TypeScript + Tailwind + shadcn/ui, with the design tokens from `docs/definition/design-guidelines.md` wired in, plus a single placeholder page proving the shell can reach the backend.

- With `frontend/` already scaffolded (0.1), run `npx shadcn@latest init`, selecting the CSS-variables-based theming option (matching design-guidelines.md §13's decision to scope tokens under `[data-theme="dark"]` / `[data-theme="light"]`, not Tailwind's default `class`-only approach). This generates `frontend/components.json`, `frontend/src/lib/utils.ts`, and wires the Tailwind config for CSS-variable-based colours. **Note:** the exact config file shape (`tailwind.config.ts` + PostCSS vs. a v4-style CSS-first `@theme` block) depends on which major Tailwind version `shadcn`'s CLI installs at implementation time — follow whatever the CLI scaffolds and adapt the token-mapping task below to that shape rather than assuming v3's file layout.
- Install `lucide-react` (icon package — zero extra integration work per design-guidelines.md §9, since it's shadcn's default).
- Install `@tanstack/react-query`.
- Add Google Fonts `<link>` tags to `frontend/index.html` for the exact family/weight strings from design-guidelines.md §4: `family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700`, `family=Inter:wght@400;500;600;700`, `family=JetBrains+Mono:wght@400;500;600`.
- Edit `frontend/src/index.css`: define every colour token from design-guidelines.md §3.1 (dark) and §3.2 (light) as CSS custom properties scoped under `[data-theme="dark"]` and `[data-theme="light"]` respectively (`--base`, `--surface`, `--elevated`, `--overlay`, `--border`, `--border-strong`, `--text`, `--text-secondary`, `--text-muted`, `--brand`, `--on-brand`, `--brand-wash`, `--brand-text`, `--success`, `--success-text`, `--success-wash`, `--error`, `--error-text`, `--error-wash`, `--warning-text`, `--warning-wash`, `--info-text`, `--info-wash`), plus the spacing scale (`--space-1` … `--space-16`, §5), border-radius scale (`--radius-sm/md/lg/xl/full`, §6), and shadow tokens (`--shadow-e1/e2/e3`, defined per-theme since dark relies on borders+lightness and light uses soft shadows, §7). Keep Tailwind's base import/directives.
- Extend the Tailwind theme config (file shape per the shadcn CLI output) to map: `colors.{base,surface,elevated,overlay,border,border-strong,text,text-secondary,text-muted,brand,on-brand,brand-wash,brand-text,success,success-text,success-wash,error,error-text,error-wash,warning-text,warning-wash,info-text,info-wash}` to `var(--token-name)`; `fontFamily.{display: Fraunces, sans: Inter, mono: "JetBrains Mono"}`; `spacing` scale to `--space-*`; `borderRadius.{sm,md,lg,xl,full}` to `--radius-*`; `boxShadow.{e1,e2,e3}` to `var(--shadow-e1/e2/e3)` (same var-indirection pattern as colours, so shadows also flip correctly per theme).
- Create `frontend/src/lib/theme.ts`: a `bootstrapTheme()` function that sets `document.documentElement.dataset.theme` to `"dark"` or `"light"` based on `window.matchMedia("(prefers-color-scheme: dark)").matches`, defaulting to `"dark"` (dark-first, per design-guidelines.md §13) if `matchMedia` is unavailable. No toggle UI yet — out of scope for Phase 0, `localStorage` override persistence is deferred to whichever phase adds a toggle control.
- Create `frontend/src/lib/api.ts`: `getHealth()` — `fetch(`${import.meta.env.VITE_API_BASE_URL}/health`)`, parses the `{data, error}` envelope, returns `data` on success, throws an `Error` with the envelope's `error.message` if `error` is non-null or the request fails.
- Edit `frontend/src/main.tsx`: call `bootstrapTheme()` before render, wrap `<App />` in a `QueryClientProvider` with a new `QueryClient()`.
- Create `frontend/src/pages/HealthCheckPage.tsx`: a centred `elevated`-background card (`radius-lg`, `shadow-e1`) containing: a Fraunces "Title" scale (23px/30px, 600) heading reading "Ask Sous", a Lucide `store` icon (24px) beside it, and a status region driven by `useQuery({ queryKey: ["health"], queryFn: getHealth })`:
  - loading → a simple "Checking backend…" caption (three-dot bounce animation is a nice-to-have, not required to pass this phase's tests — implement only if trivial, otherwise plain text is acceptable for Phase 0)
  - success → a `success-wash`/`success-text` pill (Tags/chips pattern, §8) reading the `status` value in JetBrains Mono
  - error → an `error-wash`/`error-text` pill with the caught error message
- Edit `frontend/src/App.tsx` to render `<HealthCheckPage />` as the sole content for this phase.
- Create `frontend/vitest` config (either a `test` block in `vite.config.ts` or a separate `vitest.config.ts`, `environment: "jsdom"`) and `frontend/tests/setup.ts` importing `@testing-library/jest-dom`'s matchers.

**Tasks (red-green-refactor):**
- [ ] Write a failing test (`frontend/tests/pages/HealthCheckPage.test.tsx`) mocking `getHealth` to resolve with `{ status: "ok" }`, asserting the page first renders a loading state, then renders the success pill with "ok" text
- [ ] Write a failing test in the same file mocking `getHealth` to reject, asserting the page renders the error pill with the error message
- [ ] Implement `frontend/src/pages/HealthCheckPage.tsx`, `frontend/src/lib/api.ts`, and wire `App.tsx`/`main.tsx` to make both tests pass
- [ ] Run `npx shadcn@latest init`, install `lucide-react` and `@tanstack/react-query` (scaffolding — no test)
- [ ] Add Google Fonts `<link>` tags to `index.html` (scaffolding — no test)
- [ ] Define all colour/spacing/radius/shadow CSS custom properties in `frontend/src/index.css` under `[data-theme="dark"]`/`[data-theme="light"]`, and map them in the Tailwind theme config (scaffolding — verified visually in Manual Verification, not unit-testable)
- [ ] Create `frontend/src/lib/theme.ts` and call `bootstrapTheme()` from `main.tsx` (scaffolding — verified visually)
- [ ] Refactor: if the success/error pill JSX in `HealthCheckPage.tsx` grows past two near-duplicate conditional branches, extract a reusable `frontend/src/components/StatusTag.tsx` (variant: `success` | `error` | `info` | `warning` | `neutral`, per design-guidelines.md §8) — establishes the shared tag/chip pattern Phase 3's citation chips and Phase 5's model-routing indicators will reuse

## Testing

The red-green-refactor cycle is embedded in each sub-section's tasks above. This section covers cross-cutting verification not tied to a single sub-section. Testing depth is **Practical** for Phase 0 (the Phase 1/2 stricter bar doesn't apply here).

### Integration Tests
- [ ] With the full `docker-compose` stack running and `alembic upgrade head` applied, hit `GET /health` from outside the container (not via in-process `TestClient`) and confirm the exact envelope shape end-to-end — proves the FastAPI app, its container, and its port mapping all actually work together, not just the ASGI app in isolation
- [ ] Confirm the read-only role tests from 0.3 pass against the same Postgres instance the `backend` container connects to (not a separate ad hoc test DB), so the boundary is proven against the real local topology

### Manual Verification
- [ ] `docker-compose up` — confirm both `postgres` and `backend` containers report healthy/ready in logs, with no crash loop
- [ ] `cd backend && alembic upgrade head` — confirm both migrations apply cleanly; run it a second time and confirm it's a no-op (standard Alembic idempotency)
- [ ] Connect via `psql` (or any client) using the `ask_sous_readonly` role's credentials and manually attempt `CREATE TABLE foo (id int);` — confirm it's rejected with a permissions error
- [ ] `curl http://localhost:8000/health` — confirm the JSON body is exactly `{"data": {"status": "ok"}, "error": null}`, including on repeated calls
- [ ] `cd backend && ruff check . && ruff format --check .` — confirm no errors (stands in for the `pre-commit` hook, which can't run without a `.git` directory this session)
- [ ] `cd frontend && npx biome check .` — confirm no errors (same substitution as above)
- [ ] `cd backend && pytest` and `cd frontend && npm run test` — confirm all suites pass
- [ ] Open `http://localhost:5173` with the OS set to dark mode — confirm the placeholder page renders with Warm Ember brand colour (`#ec6a3e`), Fraunces heading, Inter body text, correct card radius (`14px`) and shadow, and (once the backend is up) the success pill showing `status: ok`
- [ ] Switch the OS to light mode and reload — confirm the light-mode token set (`#c8471f` brand, `#fffaf6` base, etc.) applies correctly
- [ ] Stop the `postgres` container and reload the frontend page — confirm the page renders the error-pill state gracefully rather than crashing (proves the frontend handles a real backend failure, not just a mocked one)
- [ ] Manually inspect `.gitignore` against the actual local secret file paths (`.env`, the downloaded GCP service-account key) to confirm coverage, since `git status` can't be used to verify this without a repo yet

## User Acceptance Tests

UAT scenarios for this phase, to be added to `docs/uat.md`.

- [ ] UAT-0.1: Local environment starts successfully — Run `docker-compose up` from the project root and wait for the log output to settle. Open a web browser to `http://localhost:8000/health`. Expected: the page shows JSON text containing `"status": "ok"` inside a `data` object, with `"error": null`.
- [ ] UAT-0.2: Frontend shell loads and confirms it can reach the backend — With the backend still running from UAT-0.1, open a terminal, run `cd frontend && npm run dev`, and open the printed local URL (typically `http://localhost:5173`) in a browser. Expected: a card appears reading "Ask Sous" with a small store icon, and a green-tinted pill showing the backend's status as "ok" a moment after the page loads.
- [ ] UAT-0.3: Design system renders correctly — On the same page from UAT-0.2, check that: the heading font looks like a warm, rounded serif (not a plain sans-serif), the app background and card have a warm off-black or warm cream tone (not pure white/black or blue-grey), and the accent colour on any highlighted element is a warm orange/terracotta rather than a generic blue or red. Expected: the visual tone reads as warm and "hospitality" rather than generic tech-blue, matching the "Warm Ember" direction agreed during design.

## Documentation Updates

- [ ] Update `docs/tasks.md` with Phase 0 tasks
- [ ] Update `docs/uat.md` with UAT-0.1, UAT-0.2, UAT-0.3
- [ ] Update `docs/changelog.md` with a Phase 0 completion summary
- [ ] Write `docs/decisions/002-readonly-postgres-role.md` (ADR) documenting the read-only role creation mechanism: migration-based creation (vs. a separate init script), the conditional-create pattern (`pg_roles` lookup, since Postgres lacks `CREATE ROLE IF NOT EXISTS`), password sourced from `READONLY_DB_PASSWORD` via a genuine bind parameter, and `ALTER DEFAULT PRIVILEGES` as the mechanism that makes Phase 1's future tables automatically readable without per-table grants — plus the alternative considered (a separate shell/SQL init script run outside Alembic) and why migration-based was chosen (single source of truth for schema state, runs via the same `alembic upgrade head` command everything else uses, versioned/reversible like any other schema change).
- [ ] Update `CLAUDE.md`: name the read-only role explicitly (`ask_sous_readonly`) in the Database conventions section (currently describes the boundary without naming the role); confirm the Development Commands section matches the final commands exactly, including a note that `pre-commit install` should be run once `git init` happens; document the `code` field convention for error responses (short snake_case strings, e.g. `internal_error`, `validation_error`) since this wasn't previously specified.
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 0 as complete (add a status note under the "Phase 0: Project Foundation" heading)

## Security Considerations

This phase introduces the project's first real security-relevant mechanism: the dedicated read-only Postgres role (`ask_sous_readonly`), created in 0.3 and proven-by-test to be unable to write, insert, or create objects. This is a hard boundary per `CLAUDE.md` ("never the same credentials used by migrations/seed scripts") — Phase 2 onward will connect the agent's SQL tools exclusively through this role, so getting the grant mechanism right now (rather than patching it in later) matters.

Other security-relevant points in this phase:
- Secrets (`DATABASE_URL`, `READONLY_DB_PASSWORD`, `GOOGLE_APPLICATION_CREDENTIALS` path, GCP project/region) live only in `.env`, which is gitignored; `.env.example` holds structural placeholders only, no real values.
- The GCP service account key file itself is covered by `.gitignore` patterns (`*service-account*.json`, `*credentials*.json`, `*.key.json`) and `docs/reference/gcp-setup.md` explicitly instructs storing it outside the repo tree or in an already-ignored path.
- The global exception handler (0.4) returns a generic `"An unexpected error occurred."` message to the client for unhandled exceptions — the real exception message and traceback are logged server-side via `structlog` only, never echoed back in the HTTP response, so internal details (stack traces, file paths, query fragments) can't leak through error responses.
- New dependencies added this phase (FastAPI, SQLAlchemy, Alembic, structlog, asyncpg, Vite, React, Tailwind, shadcn/ui, TanStack Query, lucide-react) are all mainstream, actively maintained packages. Run `pip audit` (backend) and `npm audit` (frontend) once dependencies are installed, to establish a clean baseline before any further phase adds more.
- No authentication/authorisation is introduced or needed — matches master-plan.md §2 (single persona, no accounts).

## Testability

No new user roles, automated/scheduled features, or external service integrations are exercised in this phase — Vertex AI setup (`docs/reference/gcp-setup.md`) is documented as a manual checklist only, with no live API call made until Phase 3, so no sandbox/test-mode mechanism is needed yet.

The one testability-relevant groundwork this phase lays: the admin-vs-readonly Postgres credential separation (0.3) is what makes the "hard read-only boundary" claim testable at all, now and in every later phase — the `conftest.py` fixture created in 0.3 (providing both an admin and a readonly connection) is reused directly by Phase 1's and Phase 2's integration tests rather than rebuilt.

## Dependencies & Risks

- **Alembic async template first-time friction:** the async template (`alembic init -t async`) generates an `env.py` that wraps migrations in `asyncio.run(...)`, which is slightly less familiar than the sync template. Well-documented and low risk, but worth budgeting a little extra time on first setup if it's new to the builder.
- **Bind parameter placement inside role-creation SQL:** a naive approach might try to parameterise the password inside a `DO $$ ... $$` PL/pgSQL block for an "idempotent create" one-liner — this silently fails to substitute correctly, since bind-parameter substitution doesn't reach inside dollar-quoted string bodies. The plan avoids this by checking role existence via a plain `SELECT` first and only issuing a top-level, properly parameterised `CREATE ROLE ... PASSWORD :pwd` when needed. Documented in ADR-002 so this subtlety doesn't get "fixed" back into the broken pattern later.
- **Tailwind major-version ambiguity:** `stack.md` specifies "Tailwind CSS latest" without pinning a major version, and shadcn's CLI supports both v3 (PostCSS + `tailwind.config.ts`) and v4 (CSS-first `@theme`) layouts, which scaffold differently. This plan follows whatever the `shadcn@latest init` CLI actually produces at implementation time rather than assuming one file shape — flagged so the person implementing this phase checks the CLI's output before writing the token-mapping task literally as drafted.
- **pgvector image pull time:** first `docker-compose up` will pull `pgvector/pgvector:pg16`, which can take a few minutes on a slow connection. Low risk, no mitigation needed beyond patience (already the project's chosen mitigation per the implementation plan's risk register, vs. manually installing the extension).
- **GCP setup is human-gated and unverified until Phase 3:** `docs/reference/gcp-setup.md` documents the checklist, but nothing in Phase 0 actually calls Vertex AI, so a misconfigured service account (wrong role, wrong region, billing not enabled) won't surface until Phase 3 begins. Low impact on Phase 0 itself; worth doing the checklist early regardless, so it isn't a blocker when Phase 3 starts.
