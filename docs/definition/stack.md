# Ask Sous — Tech Stack Reference

**Version:** 1.0
**Date:** 2026-07-15

---

## Backend

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Backend runtime |
| FastAPI | latest 0.11x | REST API, including streaming `/chat` responses |
| Uvicorn | latest | ASGI server |
| SQLAlchemy | 2.0 (async) | ORM for app schema, migrations, seed script |
| Alembic | latest | Database migrations |
| asyncpg / SQLAlchemy `text()` | — | Parameterised raw SQL for the agent's read-only query tools (kept separate from the ORM so the exact SQL executed is always inspectable for the audit-trail story) |
| structlog | latest | Structured JSON logging — audit trail (NFR3) and general error logging |
| Faker | latest | Deterministic (fixed-seed) dummy data generation |

## Database

| Technology | Version | Purpose |
|---|---|---|
| PostgreSQL | 16 | Primary data store |
| pgvector | latest (via `pgvector/pgvector:pg16` image) | Vector similarity search over reviews and campaign copy |

## AI / Agent

| Technology | Version | Purpose |
|---|---|---|
| Vertex AI SDK (`google-genai`) | latest | Gemini Flash 2.5 (default) + Pro-tier (escalation) calls, native function-calling, streaming |
| Vertex AI embedding model | TBD at Phase 4 (see implementation-plan.md, Key Technical Decisions) | Embeddings for pgvector similarity search |

## Frontend

| Technology | Version | Purpose |
|---|---|---|
| TypeScript | 5.x | Typed frontend language |
| React | 18/19 | UI library |
| Vite | 5.x | Dev server / build tool |
| Tailwind CSS | latest | Utility-first styling |
| shadcn/ui | latest | Composable, owned-code component primitives |
| TanStack Query (React Query) | latest | Server state — fetching/caching restaurants, campaigns, chat stream state |
| Recharts | latest | Dashboard charts (Phase 7) |

## Testing

| Technology | Version | Purpose |
|---|---|---|
| pytest | latest | Backend unit/integration tests |
| Vitest | latest | Frontend unit/component tests |
| React Testing Library | latest | Frontend component test utilities |
| Playwright | latest | E2E tests (introduced from Phase 6, once a UI exists) |

## Code Quality

| Technology | Version | Purpose |
|---|---|---|
| Ruff | latest | Python linting + formatting (single tool) |
| Biome | latest | TypeScript/frontend linting + formatting (single tool) |
| pre-commit | latest | Git hook runner — Ruff + Biome checks before each commit |
| Conventional Commits | — | Commit message convention |

## Local Orchestration & Hosting

| Technology | Version | Purpose |
|---|---|---|
| Docker Compose | — | Local Postgres + FastAPI backend containers |
| Hosting | Local-only (v1) | No cloud hosting decision yet — revisit via `/first-deploy` if/when a public demo is wanted |

## External Accounts Required

| Service | Purpose | Notes |
|---|---|---|
| Google Cloud Platform project | Vertex AI (Gemini models + embeddings) | Billing must be enabled; needs to be created before Phase 3. Service account key required for local dev, kept out of git via `.gitignore` and `.env.example`. |
