---
description: Set up and run Ask Sous locally for the first time — prerequisites, environment variables, database, migrations, seed data, and both dev servers
---

# Setup

You are onboarding a new person onto the Ask Sous codebase — walking them from a fresh clone to a running app (backend + frontend + database), with as much automated as safely possible. This is a first-time setup skill, not a general development helper: assume nothing has been configured yet, and check before doing anything destructive (never overwrite an existing `.env` without asking, never drop/reset a database that already has data without confirming).

Read `README.md`'s "Running this project locally" section and `CLAUDE.md`'s Development Commands section first — they're the source of truth for exact commands; this skill's job is to *run* them for the user, checking state and explaining each step in plain language, not to duplicate that documentation from memory.

## Step 1: Check prerequisites

Check for each of these and report what's missing, with an install suggestion, before proceeding:
- `python3 --version` — needs 3.12+
- `node --version` / `npm --version` — needs Node 18+
- A local PostgreSQL 16+ install with the `pgvector` extension available (see Step 3 — this is the verified, working path; Docker Compose is not currently used or tested for this project, so don't offer it as an option)
- Whether `.env` and `frontend/.env` already exist (don't overwrite silently if they do — ask first)

If anything critical is missing, tell the user what to install and stop — don't try to install system-level tools yourself without asking.

## Step 2: Environment variables

If `.env` doesn't exist yet:
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Then walk the user through what needs real values in `.env`:
- `DATABASE_URL`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` — the defaults work for local dev as-is; only change these if the user has a reason to.
- `READONLY_DB_PASSWORD` — any value is fine; it's for a dedicated read-only Postgres role created by migration.
- `GOOGLE_APPLICATION_CREDENTIALS`/`GCP_PROJECT_ID`/`GCP_REGION` — ask whether the user already has a GCP project with Vertex AI enabled and a service account key:
  - **If yes:** help them fill in the three values (confirm the key file path exists and is readable; confirm it's *not* inside the repo tree, or if it must be, that it matches an existing `.gitignore` pattern).
  - **If no:** read `docs/reference/gcp-setup.md` for the exact checklist, then split it clearly for the user:
    - **Steps 1–2 (create/select the project, enable billing) genuinely require the [GCP Console](https://console.cloud.google.com/) in a browser and cannot be scripted.** Tell the user to do these themselves and come back with a project ID. Don't attempt to fake or skip this.
    - **Steps 3–5 (enable the Vertex AI API, create the service account with the Vertex AI User role, generate its JSON key) are plain `gcloud` CLI commands.** Check whether `gcloud` is installed (`gcloud --version`) and authenticated (`gcloud auth list` — look for an active account). If both check out, offer to run the exact commands from `docs/reference/gcp-setup.md` directly, substituting the user's project ID:
      ```bash
      gcloud services enable aiplatform.googleapis.com --project=PROJECT_ID
      gcloud iam service-accounts create ask-sous-agent --project=PROJECT_ID --display-name="Ask Sous Agent"
      gcloud projects add-iam-policy-binding PROJECT_ID \
        --member="serviceAccount:ask-sous-agent@PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/aiplatform.user"
      gcloud iam service-accounts keys create ~/secrets/ask-sous-key.json \
        --iam-account=ask-sous-agent@PROJECT_ID.iam.gserviceaccount.com
      ```
      Store the generated key **outside the repo tree** (e.g. `~/secrets/`, as above) — never inside it, even in a gitignored path, unless the user has a specific reason to. If `gcloud` isn't installed or isn't authenticated, tell the user which of those is missing and point them at the install/`gcloud auth login` step instead of trying to work around it.
    - Either way, explain that everything except live chat/campaign generation (schema, seed data, dashboard) works fine without any of this — the agent gracefully reports "unavailable" rather than crashing if these are unset. Offer to continue the rest of setup without GCP credentials and circle back later.

Never read the contents of an existing `.env` back to the user in full (it may contain real secrets) — only confirm which keys are set/unset.

## Step 3: Database

Use a local PostgreSQL install with `pgvector` — this is the verified working setup (a `docker-compose.yml` exists in the repo, but Docker itself isn't installed or tested in this environment; don't present it as an option here).

1. **Install Postgres + pgvector** if not already present:
   - macOS: `brew install postgresql@17 pgvector` (pgvector's Homebrew formula targets Postgres 17/18, not 16 — that's fine, the migration SQL itself is version-independent).
   - Start it as a background service: `brew services start postgresql@17`.
2. **Check whether the admin role/database from `.env` already exist** (`psql -h localhost -U <POSTGRES_USER> -d <POSTGRES_DB> -c "SELECT 1;"`, using the values from `.env`). If they don't, create them — the role needs `CREATE DB` privilege, matching `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` from `.env` exactly. Never invent different credentials than what's already in `.env`.
3. **Don't create the `pgvector` extension or the read-only role (`ask_sous_readonly`) yourself** — those are created by the backend's own Alembic migrations in Step 4, not a manual setup step.

## Step 4: Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed.seed
```

If GCP credentials were configured in Step 2, offer to also run `python -m app.seed.embed_seed_data` (populates semantic search embeddings — optional, takes a little longer, requires a live Vertex AI call).

Start the backend in the background and verify it's actually up:
```bash
uvicorn app.main:app --reload --port 8000
```
Confirm with `curl http://localhost:8000/health` — expect `{"data": {"status": "ok"}, "error": null}`.

## Step 5: Frontend

In parallel/after the backend is confirmed running:
```bash
cd frontend
npm install
npm run dev
```
Confirm `http://localhost:5173` responds (e.g. `curl -o /dev/null -w "%{http_code}" http://localhost:5173`).

## Step 6: Hand off

Once both servers are confirmed live, tell the user:
- The app is running at http://localhost:5173
- What they can try: asking a chat question, viewing the dashboard, generating a campaign — and that chat/campaigns need the GCP credentials from Step 2 to actually respond (otherwise they'll see a clear "agent unavailable" error, which is expected, not a bug).
- Where to run tests if they want to verify everything: `cd backend && pytest`, `cd frontend && npm run test`.
- Point them at `CLAUDE.md` for full architecture/conventions and `docs/decisions/` for the reasoning behind non-obvious design choices, if they want to go deeper.

Don't just run every command silently start-to-finish — narrate what you're doing and why at each step, since this is likely someone's first exposure to the codebase.
