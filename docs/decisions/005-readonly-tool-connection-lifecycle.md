# ADR-005: Read-Only Tool Connection Lifecycle

**Date:** 2026-07-15
**Status:** Accepted

## Context

Phase 2 is the first phase where the agent's aggregation tools actually connect to Postgres through the `ask_sous_readonly` role (ADR-002) for real feature work, not just a boundary test. `backend/app/agent/tools/db.py` needed a concrete decision: build one shared, long-lived connection (or engine) that every tool call reuses, or open a fresh one per call.

## Decision

`readonly_connection()` is an `@asynccontextmanager` that creates a brand-new `AsyncEngine` from `readonly_database_url()`, opens one connection, yields it, and disposes the engine on exit — every single call. No module-level cached engine, no connection pool held across calls.

This is deliberately the simpler, marginally less efficient option, chosen for a concrete reason: `asyncpg` connections are bound to the event loop they were created on, and this project's own test suite already hit exactly this failure once — Phase 0's `docs/changelog.md` records that a module-scoped test-fixture engine was tried as an efficiency optimization and reverted after it broke with "another operation is in progress" / cross-event-loop errors, since `pytest-asyncio` uses a fresh event loop per test function by default. A cached, long-lived engine in application code carries the identical risk the moment it's touched from a different event loop than the one that created it — which is a realistic scenario for a FastAPI app (Phase 3 onward) if the framework's request-handling lifecycle doesn't guarantee one single, stable event loop across the app's lifetime the way a naive mental model might assume.

At this project's actual scale — a handful of tool calls per agent turn, against a local Postgres instance, with a ~5-second response-time target for insights questions (master-plan.md's NFR) — the added per-call connection setup cost is negligible. Trading a small amount of raw efficiency for eliminating an entire class of event-loop bugs is the right call here.

## Consequences

- Easier: no risk of the exact cross-event-loop failure this project has already observed once; every tool function is trivially safe to call from anywhere (a test, a script, eventually a FastAPI request handler) without reasoning about which event loop created some shared engine.
- Harder: a small, currently-immaterial amount of repeated connection setup/teardown overhead per tool call, which would compound if this project's tool-call volume ever grew by orders of magnitude.

## Alternatives Considered

- **A module-level cached `AsyncEngine`, created once and reused across all calls** — rejected for the event-loop-binding risk described above, which this project has concrete, first-hand evidence of (the reverted Phase 0 optimization).
- **A connection pool scoped to the request/turn lifecycle** (e.g. created once per `/chat` request in Phase 3, threaded through to each tool call) — not rejected outright, just deferred. This is the natural next step *if* profiling ever showed the per-call engine cost actually mattered at this project's real usage volume. Nothing in this phase's design blocks adding it later; `readonly_connection()`'s signature doesn't leak the current implementation choice to callers.
