# Ask Sous

A grounded restaurant-analytics chat agent — see `docs/definition/master-plan.md` for the full product spec, and `CLAUDE.md` for project conventions.

## Development

See `CLAUDE.md`'s Development Commands section for the exact commands (Alembic, seed script, tests, dev servers), and "Running this project locally" below for a full first-time setup walkthrough.

## Commit conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, etc.) once version control is initialized.

## Running this project locally

If you're picking this project up fresh (a clone, a fork, or someone shared the repo with you), here's everything needed to get it running.

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** and npm
- **PostgreSQL 16+ with the `pgvector` extension** — a local install (e.g. `brew install postgresql@17 pgvector` on macOS; pgvector's Homebrew formula targets Postgres 17/18, which is fine since the migration SQL itself is version-independent)
- **A Google Cloud project with Vertex AI enabled** — only required for the chat/campaign-generation features to actually call a model; everything else (schema, seed data, dashboard) works without it. See `docs/reference/gcp-setup.md` for the one-time setup checklist. Two of its steps genuinely require the [GCP Console](https://console.cloud.google.com/) in a browser and can't be scripted — creating/selecting the project, and enabling billing on it. The rest (enabling the Vertex AI API, creating a service account with the Vertex AI User role, generating its JSON key) are plain `gcloud` CLI commands — if you have the [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth login`), you or an assistant can run those directly once you have a project ID; see the doc for the exact commands.

### 1. Clone and configure environment variables

```bash
git clone <this-repo-url>
cd ask-sous
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Edit the root `.env` and fill in:
- `DATABASE_URL` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` — must stay consistent with each other; the defaults work as-is for local development.
- `READONLY_DB_PASSWORD` — any value; used to create a dedicated read-only Postgres role the agent's tools connect through.
- `GOOGLE_APPLICATION_CREDENTIALS` / `GCP_PROJECT_ID` / `GCP_REGION` — from the GCP setup checklist above. **Never commit the actual key file** — store it outside the repo (e.g. `~/secrets/`).

`.env` is gitignored and never committed; `.env.example` holds only placeholders.

### 2. Database

Install Postgres + pgvector locally if you haven't already (see Prerequisites above), then start it:

```bash
brew services start postgresql@17
```

Create the admin role/database matching your `.env` values (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`) if they don't already exist — the migrations in the next step create the `pgvector` extension and the dedicated read-only role automatically, so there's nothing else to set up manually here.

### 3. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head          # run migrations
python -m app.seed.seed       # seed deterministic demo data (idempotent)
```

Optional, only if you configured GCP credentials and want semantic review/campaign search to work:

```bash
python -m app.seed.embed_seed_data
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health` should return `{"data": {"status": "ok"}, "error": null}`.

### 4. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

### 5. Try it out

- **Chat** — ask a question like "How much revenue did I make last week?" (requires Vertex AI credentials to be configured; without them you'll get a clear "agent unavailable" error, not a crash).
- **Dashboard** — select one or more restaurants from the sidebar switcher to see KPIs, or a multi-location comparison table for 2+.
- **Campaigns** — generate marketing copy for a single selected restaurant.

### Running tests

```bash
cd backend && pytest
cd frontend && npm run test
```

### More detail

- `CLAUDE.md` — full project conventions, architecture, and every command in more detail.
- `docs/reference/seed-patterns.md` — the seeded demo data's ground truth (restaurant profiles, deliberate patterns, verification queries) if you want to sanity-check the numbers you see.
- `docs/decisions/` — architecture decision records explaining the *why* behind non-obvious choices.

### Sharing this project via Claude Code

If the person you're sharing this with also uses Claude Code, this repo includes a project-level skill at `.claude/skills/setup/SKILL.md`. Once they clone the repo and open it in Claude Code, running `/setup` walks Claude through this entire checklist interactively — checking prerequisites, creating `.env` files, running migrations and the seed script, installing dependencies, and starting both dev servers — pausing only for the manual, external steps (GCP project/credentials) that can't be automated.
