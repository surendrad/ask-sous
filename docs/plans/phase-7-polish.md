# Phase 7: Polish (post-MVP) — Implementation Plan

**Date:** 2026-07-16
**Status:** Complete
**Source:** implementation-plan.md Phase 7

---

## Goal

Explicit post-MVP polish per the master plan: a live-trickle background generator that simulates ongoing activity (so a demo doesn't look frozen in time), and a simple dashboard giving the KPI/chart visual weight a data product is expected to have — neither is core to the agent story (the MVP already fully proves grounded Q&A and grounded generation), so both stay intentionally small.

## Prerequisites

- Phases 0–6 complete (MVP). Local Postgres running, migrated, seeded. Backend venv + frontend `npm install` done.
- `app/core/config.py`'s `enable_trickle: bool = False` (Phase 0) and `.env.example`'s `ENABLE_TRICKLE=false` already exist — this phase is the first to actually read that flag.

## Implementation Details

### 7.1 Live-trickle generator

`app/seed/trickle.py` — a background asyncio task, **not** reusing `generators.py`'s deterministic seeded RNG (CLAUDE.md's own convention: `trickle.py` must use genuine `uuid.uuid4()`/real randomness, since it exists specifically to simulate non-deterministic ongoing activity, unlike the reproducible seed data). Inserts one transaction (1-3 line items, current timestamp) for a randomly-chosen restaurant on each tick, via the same privileged `async_session_maker` path `seed.py` uses (this is a normal app-level write, not an agent tool — the read-only boundary doesn't apply here).

```python
async def insert_trickle_transaction(session: AsyncSession, restaurant: Restaurant, menu_items: list[MenuItem]) -> None: ...
async def run_trickle_loop(*, interval_seconds: float = 30.0) -> None: ...  # runs until cancelled
```

Wired into `app/main.py` via FastAPI's lifespan: if `settings.enable_trickle`, spawn `run_trickle_loop()` as an `asyncio.Task` on startup, cancel it on shutdown. No manual on-demand trigger endpoint — matches implementation-plan.md 7.1's "no manual on-demand trigger, per the agreed testability approach" verbatim; testability comes from calling `run_trickle_loop()` directly with a short interval and a cancellation deadline in tests, not from an HTTP-triggerable single-shot version.

**Tasks (red-green-refactor):**
- [ ] Write a failing integration test asserting `insert_trickle_transaction()` inserts exactly one transaction with a real `uuid.uuid4()` id and a `transaction_time` close to now
- [ ] Implement `insert_trickle_transaction()`
- [ ] Write a failing integration test running `run_trickle_loop(interval_seconds=0.05)` for ~3 ticks (cancelled via `asyncio.wait_for`/task cancellation) and asserting the transaction count increased by roughly that many rows
- [ ] Implement `run_trickle_loop()`
- [ ] Write a failing test asserting the lifespan does *not* start the loop when `ENABLE_TRICKLE=false` (the default) — smoke-test via `TestClient`'s startup/shutdown against a mocked `run_trickle_loop`
- [ ] Wire the lifespan in `main.py`

### 7.2 Dashboard

**Design-guidelines.md vs. implementation-plan.md's tech choice — reconciled in favor of the more specific, later decision.** implementation-plan.md 7.2 names Recharts; design-guidelines.md §11 (written during `/designer`, with this exact feature in mind) explicitly says "CSS-drawn bars, no charting library needed for the demo's visual weight." Since design-guidelines.md is the more specific, downstream artifact — and adding a charting library for two simple charts on a nice-to-have view is exactly the kind of unjustified dependency CLAUDE.md's conventions push against — this plan follows design-guidelines.md: **no Recharts, no new dependency.** Noted here rather than silently diverging from implementation-plan.md's wording.

**Backend:** `GET /dashboard?restaurant_id=...` (`backend/app/api/dashboard.py`) — no new aggregation SQL; reuses existing Phase 2 tools directly (not through the agent):
- KPIs + revenue trend: `get_revenue_summary(restaurant_id, last_7_days)` — `total_revenue`, `transaction_count`, `average_ticket` become the KPI row; `daily_breakdown` becomes the revenue-trend chart data as-is.
- Top items: `get_item_velocity(restaurant_id, last_7_days, top_n=5)`, re-sorted by `total_quantity` descending (the tool's own top-N selection is trend-strength-based, which isn't quite "top items" — the dashboard wants total volume, a one-line re-sort of the same query result rather than new SQL).

**Frontend:** `frontend/src/pages/DashboardPage.tsx` — KPI stat-card row + two chart cards, both CSS-drawn per the design guidelines: revenue trend as a 7-bar bar chart (`height` proportional to `revenue / max(revenue)`), top items as a ranked list with an inline proportional bar per row (`width` proportional to `quantity / max(quantity)`). `AppShell` gains a third view: Dashboard becomes a real, full-width view (not part of the chat/campaigns split, per design-guidelines.md §5) instead of the disabled Phase-6 placeholder — its nav button is enabled and `activeView === "dashboard"` swaps the split grid for a single full-width dashboard section.

**Tasks (red-green-refactor):**
- [ ] Write a failing integration test for `GET /dashboard` (seeded DB, asserts KPI shape + non-empty revenue trend + top items sorted by quantity)
- [ ] Implement the endpoint, register the router
- [ ] Write a failing Vitest test for `getDashboard()` in `api.ts`
- [ ] Implement it
- [ ] Write failing RTL tests for `DashboardPage` (KPI row renders, revenue bars proportional, top items list sorted/proportional, empty-data case doesn't crash)
- [ ] Implement `DashboardPage`
- [ ] Write a failing RTL test for `AppShell`'s Dashboard nav item: no longer disabled, clicking it swaps to the full-width dashboard view
- [ ] Implement the `AppShell` change, wire `DashboardPage` into `App.tsx`

## Testing

### Integration Tests
- Trickle loop: rows increase over a short run when enabled; zero rows added when disabled.
- `/dashboard`: correct shape and real seeded-data values.

### Manual Verification
- Toggle `ENABLE_TRICKLE=true` locally, watch transaction count increase over ~1 minute.
- Open the dashboard view in a real browser, confirm bars/KPIs render sensibly against seeded data.

## User Acceptance Tests

- [ ] UAT-7.1: With `ENABLE_TRICKLE=true`, transaction data visibly grows over time without any manual action
- [ ] UAT-7.2: With `ENABLE_TRICKLE=false` (default), no trickle transactions ever appear
- [ ] UAT-7.3: Dashboard view shows sensible KPIs, a 7-day revenue trend, and a top-items ranking for the selected restaurant
- [ ] UAT-7.4: Switching restaurants updates the dashboard view too (same restaurant-scoping as chat/campaigns)

## Documentation Updates

- [ ] ADR: trickle generator design + the Recharts-vs-CSS-bars reconciliation
- [ ] Update `docs/tasks.md`, `docs/uat.md`, `docs/changelog.md`, `CLAUDE.md`, `docs/definition/implementation-plan.md`

## Security Considerations

Trickle writes go through the privileged session (same credentials `seed.py` uses), not the read-only role — this is intentional and matches `seed.py`'s own precedent; the read-only boundary is specific to agent tool code, not the whole app. No new externally-triggerable write surface — trickle is purely a startup-time background task, no endpoint to invoke it.

## Dependencies & Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Trickle loop running indefinitely in dev could quietly grow the DB unbounded | Low | Low | `ENABLE_TRICKLE` defaults to `false`; this is dev/demo-only tooling, not production |
| CSS-drawn bars vs. Recharts is a real deviation from implementation-plan.md's literal wording | Low | N/A | Explicitly reconciled and documented above and in the ADR, not silent |
