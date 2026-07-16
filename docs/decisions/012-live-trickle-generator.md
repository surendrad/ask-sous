# ADR-012: Live-Trickle Generator and Dashboard Charting Approach

**Date:** 2026-07-16
**Status:** Accepted

## Context

Phase 7 is explicit post-MVP polish per the master plan: a live-trickle background generator (so a demo doesn't look frozen in time) and a simple dashboard giving the KPI/chart visual weight expected of a data product. Two implementation questions needed concrete answers this phase: how the trickle generator's randomness/lifecycle should differ from the deterministic seed data, and how to reconcile a real conflict between implementation-plan.md 7.2 (which names Recharts) and design-guidelines.md §11 (written later, during `/designer`, with this exact feature in mind — "CSS-drawn bars, no charting library needed for the demo's visual weight").

## Decision

**Trickle generator (`backend/app/seed/trickle.py`) uses genuine randomness, not the seeded RNG.** `insert_trickle_transaction()` uses Python's `random` module and `uuid.uuid4()` directly — never `generators.py`'s seeded `rng`/`rng_uuid()`. This isn't a style preference: CLAUDE.md's own convention (established in Phase 1, ADR-004) explicitly scopes deterministic seeding to `seed.py`/`generators.py` only, precisely so a future non-deterministic generator like this one wouldn't accidentally inherit reproducibility that would defeat its purpose (simulating real, ongoing, non-reproducible activity).

**No manual on-demand trigger endpoint.** `run_trickle_loop()` is a plain `while True` loop (tick, sleep, repeat) started as an `asyncio.Task` from FastAPI's `lifespan` context manager only when `settings.enable_trickle` is true, and cancelled on shutdown — matching implementation-plan.md 7.1's "no manual on-demand trigger, per the agreed testability approach" verbatim. Testability comes from calling `run_trickle_loop()` directly with a short `interval_seconds` and an injectable `session_maker` in tests (cancelling the task after a few ticks), not from adding an HTTP endpoint that would only exist to serve tests.

**Trickle writes use the same privileged session path `seed.py` uses, not `readonly_connection()`.** The agent's read-only DB boundary (ADR-002) is specific to `app/agent/` tool code; this is a normal app-level background write, with the same credentials migrations and seeding already use. No new security surface — there is still no HTTP-triggerable write path for trickle data.

**Dashboard charts: CSS-drawn bars, not Recharts — the design-guidelines.md decision wins.** design-guidelines.md is the more specific, downstream artifact (written during `/designer`, after implementation-plan.md, with this exact "revenue trend as a 7-day bar chart, top items as a ranked list with inline proportional bars" feature already in mind) and its own stated reasoning — "nice-to-have per the master plan, not core to the agent story, so it stays simple" — directly argues against adding a charting library dependency for two simple charts on a view that isn't the product's core pitch. `frontend/src/pages/DashboardPage.tsx` renders both charts as plain divs with `style={{ height/width: ... }}` proportional to the data's max value; no new npm dependency was added.

**`GET /dashboard` reuses Phase 2's existing tools directly, no new aggregation SQL.** `get_revenue_summary()` supplies both the KPI row and the revenue-trend chart data (its `daily_breakdown` is already exactly the trend shape needed); `get_item_velocity()` supplies the top-items list, re-sorted by `total_quantity` (its own top-N selection is trend-strength-based, which isn't quite the same question as "what sells the most" — a one-line re-sort of the same query result, not new SQL). This is the dashboard's own access point, not an agent tool — it's deterministic app data a human clicks a nav item to see, not something the LLM decides to fetch, so it isn't registered in `tool_registry.py` and doesn't go through `answer_question()`.

## Consequences

- `AppShell`'s Dashboard nav item, disabled as a Phase-6 placeholder, is now a real third view. Unlike Chat/Campaigns (which are two panels of one split view, always both present in the DOM, only CSS-toggled for the mobile breakpoint), switching to Dashboard **conditionally renders** the dashboard panel in place of the split — a real layout difference, not just another CSS-visibility state, matching design-guidelines.md §5's "Dashboard is a separate full-width view (not part of the split)."
- `ENABLE_TRICKLE` defaults to `false` (Phase 0); nothing about this phase changes that default. A developer who never sets it never sees a growing DB.
- Dashboard's "last 7 days" is real calendar time (`date.today()`), not the seed data's frozen end date (`SEED_END_DATE`, currently 2026-07-14). Without trickle enabled, this window only partially overlaps the seed data as real time moves past the seed's own end date — an inherent, pre-existing property of a demo with a fixed historical seed window (not something this phase introduces), and exactly the gap the trickle generator exists to keep filled when enabled.

## Alternatives Considered

- **Recharts**, per implementation-plan.md's literal wording. Rejected in favor of design-guidelines.md's later, more specific decision — see Decision above. Revisit only if the dashboard's chart needs grow past what two simple proportional-bar charts can express.
- **An HTTP endpoint to manually trigger one trickle insert**, for easier manual testing. Rejected: implementation-plan.md 7.1 explicitly calls this out as the wrong testability approach for this feature — the point is simulating passive, ongoing activity, and a manual trigger both adds an unneeded endpoint and undermines the "no manual action needed" demo story.
- **New dedicated SQL for the dashboard's top-items query** (matching total quantity sold directly, rather than reusing and re-sorting `get_item_velocity()`'s trend-oriented result). Rejected as unjustified duplication for a nice-to-have view — the existing query already returns `total_quantity` per item; re-sorting is a one-line change, not new SQL surface to write and test.
