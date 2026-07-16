# Phase 2: Aggregation Tools — Implementation Plan

**Date:** 2026-07-15
**Status:** In Progress
**Source:** implementation-plan.md Phase 2

---

## Goal

Build the four pre-built aggregation functions named in master-plan.md §4.2 — revenue summary, item velocity, day-over-day/week-over-week comparison, and peer/cohort comparison — as plain, testable async Python functions that execute parameterised SQL against the database exclusively through the `ask_sous_readonly` role (ADR-002). This is the project's first phase where that read-only boundary is used for real feature work, not just tested in isolation (Phase 0/1 only proved the role *could* read; this phase is where the agent's actual data path is built on top of it). It's also the phase most directly tied to master-plan.md §9's success metric: because Phase 3's agent will call these functions as its tools with no independent way to check their arithmetic, every number they return has to be right, and provably right against `docs/reference/seed-patterns.md`'s documented patterns — Golden Skillet's Tuesday slowdown, Bella Notte's Truffle Fries trend, and Sakura Table's premium ticket size. Phase 2 deliberately has no LLM, no function-calling schema, and no `/chat` endpoint in it — that's Phase 3's job. This phase's entire job is: given a restaurant and a date range (or two restaurants, or a window), return correct, structured numbers.

## Prerequisites

- Phase 0 complete: `ask_sous_readonly` role exists (migration `0002`), proven read-only by integration test. `backend/tests/integration/conftest.py` provides `admin_engine` and `readonly_engine` fixtures.
- Phase 1 complete: full schema (`backend/app/db/models.py`), seeded database with the three deliberate patterns and two control restaurants. `docs/reference/seed-patterns.md` is the ground-truth reference this phase's tests are checked against.
- A running local Postgres instance (Homebrew Postgres 17 + pgvector, per the Phase 0 deviation — Docker is not available in this implementation environment) with migrations applied and the database seeded (`cd backend && alembic upgrade head && python -m app.seed.seed`). All "run this against the database" tasks below are written generically and apply to whichever local Postgres instance `DATABASE_URL` points at.
- Backend virtualenv active, dependencies installed (`pip install -e ".[dev]"` from `backend/`). No new runtime dependencies are needed this phase — Phase 2 is pure Python + SQLAlchemy `text()`, already in `pyproject.toml`.
- No GCP/Vertex AI setup required — no live model calls happen until Phase 3.

## Implementation Details

### 2.1 Read-only DB connection path for tools

A new module, `backend/app/agent/tools/db.py`, is the single place agent tool code opens a database connection — separate from `backend/app/db/session.py`'s admin-credentialed `async_session_maker`, which migrations and the seed script use. Every aggregation tool in this phase (and, from Phase 3 onward, the raw SQL tool and pgvector search tool) goes through this module and nothing else. This is the literal implementation of the boundary CLAUDE.md and ADR-002 describe as "a hard boundary, not a convention to relax under time pressure."

**Design:** `readonly_database_url()` builds the `ask_sous_readonly` connection URL by taking the admin `settings.database_url` and swapping only the username/password (same host/port/database) — the same technique already established in `backend/tests/integration/conftest.py`'s `readonly_engine` fixture, now promoted to real application code so tests and features share one mental model of "how do we even get a readonly connection." `readonly_connection()` is an `asynccontextmanager` that creates a fresh `AsyncEngine` from that URL, opens one connection, yields it, and disposes the engine on exit — a new engine per call, not a module-level cached singleton. This is a deliberate simplicity choice worth stating plainly: `pytest-asyncio` uses a fresh event loop per test function by default (already the documented reason `admin_engine`/`readonly_engine` in `conftest.py` are function-scoped, not module-scoped — Phase 0's changelog records that a module-scoped-engine optimization was tried and reverted for exactly this reason), and `asyncpg` connections are bound to the event loop they were created on. A cached, long-lived engine at module scope would risk the same "attached to a different loop" failure the moment tests or FastAPI's own lifecycle touched it from a different loop. At this project's scale — a handful of tool calls per agent turn, against a local Postgres instance, with a ~5s response-time target — the extra per-call connection setup cost is negligible, so trading a small amount of raw efficiency for eliminating an entire class of event-loop bugs is the right call here. If profiling ever showed this mattered, a connection-pool-aware version scoped to the request/turn lifecycle would be the fix — not a bare module-level cache.

`Settings` (`backend/app/core/config.py`) currently has no typed field for the read-only role's password — `os.environ["READONLY_DB_PASSWORD"]` is read directly by the migration and by `conftest.py`'s test fixture, but there's no fail-fast, typed path for real application code. This phase adds one, consistent with the project's existing "fail fast at startup" convention for every other required setting.

**Tasks (red-green-refactor):**
- [ ] Write a failing unit test (`backend/tests/unit/test_config.py`, extending the existing file) asserting `Settings()` raises `ValidationError` when `READONLY_DB_PASSWORD` is unset, and loads successfully with it present, matching the pattern already used for `database_url`/GCP vars
- [ ] Add `readonly_db_password: str` to `Settings` in `backend/app/core/config.py` to make the test pass (pydantic-settings maps it from the `READONLY_DB_PASSWORD` env var by field name, same as every other field already does)
- [ ] Write a failing unit test (`backend/tests/unit/test_agent_tools_db.py`) asserting `readonly_database_url()` — constructed against a monkeypatched `Settings` object with known fake values — produces a URL whose username is `app.core.config.READONLY_DB_ROLE` (`"ask_sous_readonly"`) and whose password matches `settings.readonly_db_password`, while host/port/database match the admin `database_url`'s host/port/database
- [ ] Write a failing unit test in the same file asserting the built readonly URL's username/password differ from the admin `database_url`'s username/password (proves it's a genuinely different credential, not an alias pointing at the same login) — no real DB connection needed for either test
- [ ] Implement `backend/app/agent/tools/db.py`: `readonly_database_url() -> str` and `readonly_connection()` (an `@asynccontextmanager` async generator yielding an `AsyncConnection`), exactly as designed above, to make both unit tests pass
- [ ] Write a failing integration test (`backend/tests/integration/test_agent_tools_db.py`) asserting: (a) `readonly_connection()` yields a connection that can run `SELECT current_user` and get back exactly `"ask_sous_readonly"`; (b) the same connection can `SELECT COUNT(*) FROM restaurants` without error; (c) the same connection raises (`InsufficientPrivilege`/`asyncpg.exceptions.InsufficientPrivilegeError`) on `INSERT INTO restaurants (name) VALUES ('test')` — proving this specific module's connection path is genuinely read-only, not just the role in the abstract (already proven by Phase 0/1's own tests)
- [ ] Run the integration test against the local Postgres instance; fix anything surfaced (expected to pass first try if 2.1's implementation matches the design above)
- [ ] Extend `backend/tests/integration/conftest.py` with a `seeded_restaurants` fixture: seeds the database (`seed_database()` via the existing `admin_engine` fixture), then queries back and returns a `dict[str, uuid.UUID]` mapping each of the 5 restaurant names to its id — every tool's integration test in 2.2–2.6 depends on this instead of each test re-seeding and re-querying restaurant ids independently. Follows the exact "re-seed at the top of the test/fixture" pattern already used by Phase 1's `test_pipeline.py`, since the local dev database's current state shouldn't be assumed stable across test runs (documented risk in `docs/plans/phase-1-data-layer.md`'s Dependencies & Risks)
- [ ] Refactor: confirm `db.py` imports `READONLY_DB_ROLE` from `app.core.config` rather than hardcoding the role name a second time, and that no other file in `app/agent/` imports `app.db.session` (the admin-credentialed path) — grep for `from app.db.session` outside `app/db/` and `app/seed/` to confirm

### 2.2 Revenue summary tool

`backend/app/agent/tools/revenue_summary.py`. Answers "how much did this restaurant make, and how many transactions, over this date range" — the base building block every other tool in this phase either calls directly (`compare_periods`, 2.4) or mirrors the query shape of (`get_item_velocity`, `get_cohort_comparison`).

Following the pure/impure split CLAUDE.md's Phase 1 precedent established (`generators.py` pure vs. `seed.py` orchestration), the module splits into a pure row-summarising function (unit-testable with fixture data, no DB) and a thin async function that fetches rows via SQL and calls it:

```python
@dataclass(frozen=True)
class DailyRevenue:
    day: date
    transaction_count: int
    revenue: Decimal

@dataclass(frozen=True)
class RevenueSummary:
    restaurant_id: uuid.UUID
    start_date: date
    end_date: date
    total_revenue: Decimal
    transaction_count: int
    average_ticket: Decimal
    daily_breakdown: list[DailyRevenue]

def _summarize_daily_rows(
    restaurant_id: uuid.UUID, start_date: date, end_date: date, rows: Sequence[DailyRevenue]
) -> RevenueSummary: ...  # pure — totals, average ticket (0 if no transactions, never a ZeroDivisionError)

async def get_revenue_summary(
    restaurant_id: uuid.UUID, start_date: date, end_date: date
) -> RevenueSummary: ...  # opens its own readonly_connection(), runs the SQL below, calls _summarize_daily_rows
```

SQL (parameterised, `text()`, no dynamic identifiers):

```sql
SELECT transaction_time::date AS day, COUNT(*) AS transaction_count, SUM(total_amount) AS revenue
FROM transactions
WHERE restaurant_id = :restaurant_id
  AND transaction_time::date BETWEEN :start_date AND :end_date
GROUP BY transaction_time::date
ORDER BY transaction_time::date
```

`daily_breakdown` is the deliberate design choice that makes this tool double as the building block for day-of-week analysis: a caller (agent, or this phase's own correctness tests) groups the returned days by `.day.weekday()` to compute e.g. "average Tuesday revenue vs. average revenue on other days" without a second, bespoke query. This keeps the tool itself simple (one query shape, one grouping level) while still making Golden Skillet's pattern detectable through it, per implementation-plan.md's framing of this tool as part of what's needed for "why was revenue down" questions.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_revenue_summary.py`) for `_summarize_daily_rows()` against small fixture `DailyRevenue` lists (no DB): correct `total_revenue`/`transaction_count` sums; `average_ticket` computed as `total_revenue / transaction_count`; empty `rows` list produces `total_revenue == Decimal("0")`, `transaction_count == 0`, `average_ticket == Decimal("0")` (not a `ZeroDivisionError`); `daily_breakdown` on the returned object is exactly the input rows, unmodified
- [ ] Implement `_summarize_daily_rows()` in `backend/app/agent/tools/revenue_summary.py` to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_revenue_summary_integration.py`) asserting `get_revenue_summary()` against a restaurant/date-range with **zero** transactions (e.g. a date range entirely before the 90-day seed window) returns a `RevenueSummary` with all-zero totals and an empty `daily_breakdown`, without error
- [ ] Implement `get_revenue_summary()` (SQL + `readonly_connection()` + `_summarize_daily_rows()`) to make it pass
- [ ] Refactor: confirm the SQL string is a module-level `text(...)` constant (not rebuilt per call) and that `get_revenue_summary()` contains no branching logic beyond "fetch rows, delegate to the pure function"

### 2.3 Item velocity tool

`backend/app/agent/tools/item_velocity.py`. Answers "is this item trending up or down" by splitting a window into a first half and second half and comparing quantity sold between them — this is exactly what Bella Notte's Truffle Fries pattern needs to be detectable through, and generalises to any menu item at any restaurant.

```python
@dataclass(frozen=True)
class ItemVelocity:
    menu_item_id: uuid.UUID
    menu_item_name: str
    category: str
    window_start: date
    window_end: date
    first_half_quantity: int
    second_half_quantity: int
    total_quantity: int
    quantity_change_pct: Decimal | None  # None when first_half_quantity == 0 (undefined % change)
    trend: str  # "up" | "down" | "flat"

TREND_THRESHOLD_PCT = Decimal("15")  # +/- 15 percentage points before calling it a real trend, not noise

def _window_midpoint(window_start: date, window_end: date) -> date: ...  # pure

def _build_item_velocities(
    window_start: date, window_end: date, rows: Sequence[tuple], *, top_n: int | None
) -> list[ItemVelocity]: ...  # pure — buckets daily per-item rows into halves, computes pct change + trend, sorts, truncates

async def get_item_velocity(
    restaurant_id: uuid.UUID,
    window_start: date,
    window_end: date,
    *,
    menu_item_name: str | None = None,
    top_n: int | None = None,
) -> list[ItemVelocity]: ...
```

SQL fetches **daily** per-item quantities (not pre-bucketed into halves in SQL) so all bucketing/trend logic stays in the pure, unit-testable function:

```sql
SELECT t.transaction_time::date AS day, m.id AS menu_item_id, m.name AS menu_item_name,
       m.category AS category, SUM(ti.quantity) AS quantity
FROM transaction_items ti
JOIN transactions t ON t.id = ti.transaction_id
JOIN menu_items m ON m.id = ti.menu_item_id
WHERE t.restaurant_id = :restaurant_id
  AND t.transaction_time::date BETWEEN :window_start AND :window_end
  AND (:menu_item_name IS NULL OR m.name = :menu_item_name)
GROUP BY t.transaction_time::date, m.id, m.name, m.category
```

`menu_item_name` is compared via a genuine bind parameter (`m.name = :menu_item_name`), never string-interpolated — satisfies CLAUDE.md's "no dynamic table/column names built from LLM output" rule (this is a *value* comparison, not an identifier).

**Bucketing rule** (`_window_midpoint`): `midpoint = window_start + (window_end - window_start) // 2 + 1 day`; days `< midpoint` are "first half", days `>= midpoint` are "second half" — for a 90-day window this is an even 45/45 split. **Trend labelling:** an item with `first_half_quantity == 0` and `second_half_quantity > 0` is "up" with `quantity_change_pct = None` (an undefined/infinite increase, sorted as the strongest possible "up" signal); the reverse is "down" with `quantity_change_pct = None`; an item with zero quantity in *both* halves is dropped from the result entirely (no signal to report); otherwise `quantity_change_pct = (second - first) / first * 100`, and `trend` is `"up"` if `> TREND_THRESHOLD_PCT`, `"down"` if `< -TREND_THRESHOLD_PCT`, else `"flat"`. Results are sorted by `quantity_change_pct` descending (undefined/"infinite up" first), then truncated to `top_n` if given.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_item_velocity.py`) for `_window_midpoint()`: even-length window splits exactly in half; odd-length window puts the extra day in the second half
- [ ] Implement `_window_midpoint()` to make it pass
- [ ] Write failing unit tests for `_build_item_velocities()` against a small fixture row set (~5 synthetic items across a 10-day window, `midpoint` at day 5): an item with steady low-then-high quantity is labelled `"up"` with the correct `quantity_change_pct`; a flat item (same quantity both halves) is labelled `"flat"`; an item present only in the second half is labelled `"up"` with `quantity_change_pct is None`; an item present only in the first half is labelled `"down"` with `quantity_change_pct is None`; an item with zero rows in the window entirely doesn't appear in fixture input, confirming there's nothing to accidentally include; `top_n=2` returns only the two highest-ranked items in `quantity_change_pct`-descending order (with `None`/infinite-up items sorted first)
- [ ] Implement `_build_item_velocities()` to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_item_velocity_integration.py`) asserting `get_item_velocity()` for a restaurant/window with zero matching transaction_items (e.g. `menu_item_name` that doesn't exist at that restaurant) returns an empty list, no error
- [ ] Implement `get_item_velocity()` (SQL + `readonly_connection()` + `_build_item_velocities()`) to make it pass
- [ ] Refactor: confirm the SQL's `menu_item_name` filter uses `:menu_item_name` as a genuine bind parameter and that no f-string/`.format()` touches the SQL text anywhere in this module

### 2.4 Period comparison tool (day-over-day / week-over-week)

`backend/app/agent/tools/period_comparison.py`. Answers "how did this period do against the period right before it" — a single, general tool that handles day-over-day (a 1-day period) and week-over-week (a 7-day period) as the same mechanism at different granularities, per implementation-plan.md's naming of both under one bullet. This is the tool that answers "why was revenue down" for a specific day or week by giving a directly comparable prior baseline, complementing 2.2's `daily_breakdown` (which shows the *shape* of a range) with an explicit before/after comparison.

```python
@dataclass(frozen=True)
class PeriodComparison:
    restaurant_id: uuid.UUID
    current_start: date
    current_end: date
    current_revenue: Decimal
    current_transaction_count: int
    prior_start: date
    prior_end: date
    prior_revenue: Decimal
    prior_transaction_count: int
    revenue_change_pct: Decimal | None  # None when prior_revenue == 0 (undefined % change)

def _prior_period(period_start: date, period_end: date) -> tuple[date, date]: ...  # pure

def _compare(
    restaurant_id: uuid.UUID, current: RevenueSummary, prior: RevenueSummary
) -> PeriodComparison: ...  # pure — combines two RevenueSummary objects, computes revenue_change_pct

async def compare_periods(
    restaurant_id: uuid.UUID, period_start: date, period_end: date
) -> PeriodComparison: ...  # calls get_revenue_summary() twice (current, prior) and _compare()
```

`_prior_period` computes an immediately-preceding period of the exact same length: `period_length = (period_end - period_start).days + 1`; `prior_end = period_start - 1 day`; `prior_start = prior_end - (period_length - 1) days`. This makes a 1-day period compare against the single day before it (day-over-day), and a 7-day period compare against the 7 days before it (week-over-week), with no separate code path for either — the caller's period length is what determines the granularity. `compare_periods()` reuses `get_revenue_summary()` from 2.2 rather than duplicating its SQL — two calls, two independent `readonly_connection()`s — which is the simplest correct thing to do at this project's scale and keeps 2.2's totals/average-ticket logic defined in exactly one place.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_period_comparison.py`) for `_prior_period()`: a single-day period (`period_start == period_end`) returns the single day immediately before it; a 7-day period returns the 7-day period immediately before it (correct start/end, no off-by-one); a period is never assumed to start on a Monday — arbitrary start/end dates both work
- [ ] Implement `_prior_period()` to make these pass
- [ ] Write failing unit tests for `_compare()`, constructing fixture `RevenueSummary` objects directly (no DB): `revenue_change_pct` computed correctly for a revenue increase and a revenue decrease; `prior.total_revenue == Decimal("0")` produces `revenue_change_pct is None`, not a `ZeroDivisionError`; `current_start`/`current_end`/`prior_start`/`prior_end` on the result exactly match the input summaries' `start_date`/`end_date`
- [ ] Implement `_compare()` to make these pass
- [ ] Write a failing integration test (`backend/tests/integration/test_period_comparison_integration.py`) asserting `compare_periods()` for a period entirely before the seed window (zero transactions on both sides) returns `current_revenue == prior_revenue == Decimal("0")` and `revenue_change_pct is None`, no error
- [ ] Implement `compare_periods()` (two `get_revenue_summary()` calls + `_compare()`) to make it pass
- [ ] Refactor: confirm `compare_periods()` contains no SQL of its own — it only orchestrates two `get_revenue_summary()` calls and a pure combiner

### 2.5 Peer/cohort comparison tool

`backend/app/agent/tools/cohort_comparison.py`. Answers "how does this restaurant compare to its peers" on a chosen metric — this is exactly what Sakura Table's premium-ticket pattern needs to be detectable through, and is the one tool in this phase whose SQL varies its aggregate expression based on an argument, which is exactly the case CLAUDE.md's "no dynamic table/column names built from LLM output" rule exists to guard against. The guard here: the aggregate expression is selected from a small, hardcoded allow-list dict keyed by a closed set of metric names — never built from a raw string via f-string/`.format()` — and the function raises `ValueError` at runtime for any metric outside that allow-list, since Phase 3's function-calling schema will eventually hand this function a plain string parsed from the model's tool-call arguments, and a `Literal["..."]` type hint alone provides no runtime protection against that.

```python
CohortMetric = Literal["average_ticket", "total_revenue", "transaction_count"]

_METRIC_EXPRESSIONS: dict[str, str] = {
    "average_ticket": "AVG(total_amount)",
    "total_revenue": "SUM(total_amount)",
    "transaction_count": "COUNT(*)",
}

@dataclass(frozen=True)
class CohortComparison:
    restaurant_id: uuid.UUID
    restaurant_name: str
    metric: str
    start_date: date
    end_date: date
    restaurant_value: Decimal
    peer_value: Decimal              # pooled across all other restaurants — not an average-of-averages
    peer_restaurant_count: int
    ratio_to_peers: Decimal | None   # restaurant_value / peer_value; None if peer_value == 0

def _ratio(restaurant_value: Decimal, peer_value: Decimal) -> Decimal | None: ...  # pure

async def get_cohort_comparison(
    restaurant_id: uuid.UUID,
    start_date: date,
    end_date: date,
    metric: CohortMetric = "average_ticket",
) -> CohortComparison: ...
```

SQL, with `expression` substituted from the hardcoded dict above (never from raw caller input) and every actual value still bound normally:

```sql
SELECT (r.id = :restaurant_id) AS is_target, {expression} AS metric_value
FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id
WHERE t.transaction_time::date BETWEEN :start_date AND :end_date
GROUP BY is_target
```

`peer_value` is deliberately the **pooled** aggregate across all other restaurants' transactions in the same date range (`AVG(total_amount)` computed once over every peer transaction combined), not an average of each peer restaurant's own average — this matches `docs/reference/seed-patterns.md`'s own verification query exactly (`GROUP BY is_sakura`, not `GROUP BY restaurant_id` then averaged), so this tool's output is directly checkable against the documented numbers. `get_cohort_comparison()` also runs a small second query (`SELECT name FROM restaurants WHERE id = :restaurant_id`) to populate `restaurant_name`, and a `SELECT COUNT(*) FROM restaurants WHERE id != :restaurant_id` for `peer_restaurant_count`.

**Tasks (red-green-refactor):**
- [ ] Write failing unit tests (`backend/tests/unit/test_cohort_comparison.py`) for `_ratio()`: correct division for representative values; `peer_value == Decimal("0")` produces `None`, not a `ZeroDivisionError`
- [ ] Implement `_ratio()` to make these pass
- [ ] Write a failing unit test asserting `get_cohort_comparison(restaurant_id, start, end, metric="not_a_real_metric")` raises `ValueError` *before* attempting any database call (assert via monkeypatching `readonly_connection` to a stub that fails the test if invoked, proving the validation happens first) — this needs no real DB connection since the failure path never reaches SQL
- [ ] Implement the allow-list validation (`if metric not in _METRIC_EXPRESSIONS: raise ValueError(...)`) at the top of `get_cohort_comparison()` to make it pass
- [ ] Write a failing integration test (`backend/tests/integration/test_cohort_comparison_integration.py`) asserting `get_cohort_comparison()` for a date range with zero transactions everywhere returns `restaurant_value == peer_value == Decimal("0")` and `ratio_to_peers is None`, no error
- [ ] Implement the full `get_cohort_comparison()` (SQL + the two supporting lookups + `_ratio()`) to make it pass
- [ ] Refactor: confirm `_METRIC_EXPRESSIONS` is the *only* place SQL fragments are chosen by argument value anywhere in `app/agent/tools/`, and add an inline comment at its definition explaining why this is safe (fixed, reviewed, hardcoded set — never built from caller-supplied text) so a future contributor doesn't "simplify" it into an f-string

### 2.6 Correctness verification against seed patterns

This sub-section is cross-cutting: it's where each tool built in 2.2–2.5 is proven correct against the exact patterns `docs/reference/seed-patterns.md` documents, using the `seeded_restaurants` fixture from 2.1. Per CLAUDE.md and implementation-plan.md, this phase is held to the same stricter testing bar as Phase 1, since aggregation-tool correctness is the project's core success metric (master-plan.md §9). Every threshold below uses a safety margin *below* the documented actual figures (the same "margin under the designed effect" approach Phase 1's own tests used, e.g. asserting "at least 30% below" against a designed ~59% gap) — this keeps tests robust to the small amount of Gaussian noise baked into the seed generator, without ever contradicting the numbers already published in `seed-patterns.md`.

- **Golden Skillet — Tuesday slowdown, via `get_revenue_summary()` (2.2):** call `get_revenue_summary(golden_skillet_id, SEED_START_DATE, SEED_END_DATE)` (computed as `generators.SEED_END_DATE - timedelta(days=generators.SEED_WINDOW_DAYS - 1)` through `generators.SEED_END_DATE`, importing both constants rather than hardcoding the window). Group `daily_breakdown` by `.day.weekday()` (Python: Monday=0 … Sunday=6, so Tuesday=1 — note this differs from Postgres's `EXTRACT(DOW)` convention used in `seed-patterns.md`'s own SQL, where Tuesday=2; the test computes its own grouping in Python, so this is just a reminder not to copy the DOW number literally across the two). Assert Tuesday's average `revenue` is **at least 40% below** the average of the other six weekdays — comfortably under the documented ~57.7% gap.
- **Golden Skillet — Tuesday slowdown, via `compare_periods()` (2.4):** pick a Tuesday roughly in the middle of the seed window (at least 10 days in, so its prior Monday is also inside the window) and call `compare_periods(golden_skillet_id, that_tuesday, that_tuesday)`. Assert `prior_start == prior_end == that_tuesday - 1 day` (the Monday immediately before it), and assert `revenue_change_pct <= Decimal("-25")` — i.e. that single Tuesday's revenue is at least 25% below the immediately preceding Monday. (Expected gap from the generator's own multipliers is roughly 50% — Monday's day-of-week multiplier is 0.90 vs. Tuesday's effective 0.45 — but a single-day comparison carries more noise than a 90-day-aggregated average, hence the more conservative 25% floor here vs. 40% above.)
- **Casa Verde — control, via `get_revenue_summary()`:** the same weekday-grouping check as Golden Skillet's, but asserting Casa Verde's Tuesday average is **within ±20% of** its all-week average — proving the suppression logic in `get_revenue_summary()`/its grouping is restaurant-specific behaviour being correctly surfaced, not an artifact of the tool itself (e.g. an accidental off-by-one in date handling that would suppress *some* weekday for *every* restaurant).
- **Bella Notte — Truffle Fries trend, via `get_item_velocity()`'s own halves-based trend (2.3):** call `get_item_velocity(bella_notte_id, SEED_START_DATE, SEED_END_DATE, menu_item_name=generators.TRUFFLE_FRIES_ITEM_NAME)`. Assert the result is a single-item list, `trend == "up"`, and `second_half_quantity >= 1.7 * first_half_quantity` (the tool's even 45/45 halves split yields a mathematically different, but still clearly-trending, ratio than `seed-patterns.md`'s first-30/last-30-with-middle-excluded methodology — averaging the ramp formula `p(day) = 0.05 + 0.30 * day/89` over each 45-day half gives an expected ratio of ≈2.2x, so 1.7x is a safe margin under that, not a re-statement of the document's ~3.0x figure).
- **Bella Notte — Truffle Fries trend, matching `seed-patterns.md`'s exact methodology:** call `get_item_velocity()` twice more, once for `[SEED_START_DATE, SEED_START_DATE + 29 days]` (first 30 days) and once for `[SEED_END_DATE - 29 days, SEED_END_DATE]` (last 30 days), both filtered to Truffle Fries. Compare `.total_quantity` between the two calls (a window-total field, unaffected by the tool's internal halves split) and assert `last_30_total >= 2 * first_30_total` — this is a direct, apples-to-apples cross-check against `seed-patterns.md`'s own documented 363 → 1,096 (~3.0x) result, using the exact same bucketing the document describes.
- **Sakura Table — premium ticket size, via `get_cohort_comparison()` (2.5):** call `get_cohort_comparison(sakura_table_id, SEED_START_DATE, SEED_END_DATE, metric="average_ticket")`. Assert `ratio_to_peers >= Decimal("1.5")` — above the "at least 1.3x" bar named in `implementation-plan.md`/`seed-patterns.md`, comfortably below the documented actual ~2.1x.
- **Golden Skillet or Casa Verde — control contrast, via `get_cohort_comparison()`:** call the same tool for a non-premium restaurant (e.g. Golden Skillet) over the same window and assert its `ratio_to_peers` is clearly lower than Sakura Table's (e.g. `< Decimal("1.3")`) — note this is *not* asserted to be "close to 1.0", since the peer group for a non-Sakura restaurant still includes Sakura Table itself, which pulls the peer average up; the test only asserts the *contrast* between Sakura's ratio and a control's ratio, which is the actually meaningful, non-circular claim.
- **`metric="total_revenue"` and `metric="transaction_count"`, sanity only:** one call each (any restaurant, the full seed window) asserting the returned `restaurant_value`/`peer_value` are non-negative `Decimal`s and `peer_restaurant_count == 4` — lighter-touch coverage since these aren't the seeded deliberate pattern, just confirming the allow-listed SQL fragments for the other two metrics actually execute correctly, not just `average_ticket`.

**Read-only boundary, proven for this phase's actual tool code (not re-testing the boundary itself, which Phase 0/1 already proved):**

- [ ] Write a failing integration test (`backend/tests/integration/test_aggregation_tools_readonly_boundary.py`) asserting `readonly_connection()` reports `current_user == "ask_sous_readonly"` — reused directly from 2.1's own test if that coverage already exists; otherwise added here as a cross-cutting anchor test the next four checks build on
- [ ] Write failing tests, one per tool module, monkeypatching that module's imported `readonly_connection` name (e.g. `app.agent.tools.revenue_summary.readonly_connection`) with an `AsyncMock`/spy that wraps the real implementation, calling the corresponding tool function once against seeded data, and asserting the spy was invoked exactly once — proving `get_revenue_summary()`, `get_item_velocity()`, `compare_periods()` (via its two `get_revenue_summary()` calls), and `get_cohort_comparison()` each genuinely go through this module's connection path, not an accidentally-imported admin session
- [ ] Implement/fix as needed to make these pass (expected to already pass if 2.1–2.5 are implemented as designed — this is a verification task)

**Tasks (red-green-refactor) — pattern-detection tests themselves:**
- [ ] Write the failing integration tests for all seven pattern-detection bullets above (`backend/tests/integration/test_revenue_summary_integration.py`, `test_item_velocity_integration.py`, `test_period_comparison_integration.py`, `test_cohort_comparison_integration.py` — extending the files already created in 2.2–2.5's own tasks, not new files, so each tool's "empty range" test and its "seed-pattern" tests live together)
- [ ] Run them against the local, seeded Postgres instance; if any threshold is unexpectedly close to failing, widen the margin (not the underlying generator) per the same policy Phase 1's Dependencies & Risks section established — the fix for flakiness is always a wider test margin or a documented generator-constant change, never a silently lowered bar
- [ ] Refactor: confirm every hardcoded threshold in these tests has an inline comment explaining which documented `seed-patterns.md` figure it's a safety-margined version of, so nobody reading the test in isolation has to reverse-engineer why "40%" or "1.5x" was chosen

## Testing

The red-green-refactor cycle is embedded in each sub-section's tasks above (2.1–2.6). This section covers the cross-cutting integration verification and manual checks that aren't tied to a single sub-section. Testing depth for this phase is the **stricter bar**, matching Phase 1 — every aggregation function is proven against real seeded data and hand-computable, documented thresholds, not just "doesn't crash."

### Integration Tests
- [ ] Full-suite pass: `cd backend && pytest` runs every unit and integration test from this phase alongside Phase 0/1's existing suite, with no regressions — the `seeded_restaurants` fixture's re-seed at the top of the relevant test session shouldn't corrupt or interfere with Phase 1's own seed-integration tests when run in the same `pytest` invocation
- [ ] Cross-tool consistency check: for Golden Skillet over the full seed window, assert `get_revenue_summary()`'s `total_revenue` equals the sum of `daily_breakdown[*].revenue` exactly (`Decimal`-equal, no floating-point tolerance needed) — a basic internal-consistency guard, since this is the number every other tool in this phase (and, later, the agent) implicitly trusts
- [ ] Cross-tool consistency check: `compare_periods()`'s `current_revenue` for a given period exactly matches a direct `get_revenue_summary()` call for that same period (proves 2.4 isn't silently duplicating/diverging from 2.2's SQL)

### Manual Verification
- [ ] With the database migrated and seeded, open a Python REPL (`cd backend && python -m asyncio` or a short throwaway script) and call each of the four tool functions directly against Golden Skillet, Bella Notte, and Sakura Table; visually compare the printed dataclass output against the exact numbers in `docs/reference/seed-patterns.md`
- [ ] Confirm no tool function ever imports `app.db.session` — `grep -rn "from app.db.session\|import app.db.session" backend/app/agent/` should return nothing
- [ ] `cd backend && ruff check . && ruff format --check .` — confirm no errors
- [ ] `cd backend && pytest` — confirm the full suite (Phase 0/1's existing tests plus this phase's new ones) passes

## User Acceptance Tests

UAT scenarios for this phase, to be added to `docs/uat.md`. Phase 2 still has no UI or API endpoint (that's Phase 3), so — matching the precedent set by Phase 0/1's UAT entries — these are framed as exact, followable steps against a Python REPL/script rather than a browser.

- [ ] UAT-2.1: The revenue summary tool correctly detects Golden Skillet's Tuesday slowdown — With the backend environment set up, migrations applied, and the database seeded, run a short Python script (or REPL session) that calls `get_revenue_summary()` for Golden Skillet across the full 90-day seed window and prints the average revenue per day of week. Expected: Tuesday's average is visibly, substantially lower than every other day of the week — consistent with the ~57.7%-below-average figure documented in `docs/reference/seed-patterns.md`.
- [ ] UAT-2.2: The item velocity tool correctly detects Bella Notte's Truffle Fries trend — Run a script calling `get_item_velocity()` for Bella Notte's Truffle Fries, once over the first 30 days of the seed window and once over the last 30 days, and print both `total_quantity` values. Expected: the last-30-days quantity is at least double (documented as ~3.0x) the first-30-days quantity.
- [ ] UAT-2.3: The cohort comparison tool correctly detects Sakura Table's premium ticket size — Run a script calling `get_cohort_comparison()` for Sakura Table with `metric="average_ticket"` over the full seed window, and print `restaurant_value`, `peer_value`, and `ratio_to_peers`. Expected: Sakura Table's average ticket is at least 1.3x (documented as ~2.1x) the pooled average of the other four restaurants.
- [ ] UAT-2.4: The period comparison tool explains a specific slow day — Run a script calling `compare_periods()` for a Tuesday at Golden Skillet (any Tuesday well inside the 90-day window) and print `current_revenue`, `prior_revenue`, and `revenue_change_pct`. Expected: the tool reports that Tuesday's revenue is meaningfully (at least 25%, typically much more) below the immediately preceding Monday's — a concrete, hand-checkable answer to "why was revenue down that day."

## Documentation Updates

- [ ] Update `docs/tasks.md` with Phase 2 tasks
- [ ] Update `docs/uat.md` with UAT-2.1 through UAT-2.4
- [ ] Update `docs/changelog.md` with a Phase 2 completion summary
- [ ] Write `docs/decisions/005-readonly-tool-connection-lifecycle.md` (ADR) — see Dependencies & Risks below for the decision content to record: per-call engine creation/disposal in `readonly_connection()` vs. a cached module-level engine, and why (event-loop binding risk, negligible cost at this project's scale, revisit only if profiling says so)
- [ ] Update `CLAUDE.md`: note that `backend/app/agent/tools/db.py` is now the concrete implementation of the read-only boundary described in the Database conventions section (currently describes the boundary abstractly via ADR-002 but doesn't name the module agent code actually imports); add a short line under Agent/grounding noting the pure/impure split convention (`_build_x()`/`_summarize_x()` pure functions vs. thin `async def get_x()` wrappers) now established in `app/agent/tools/`, so Phase 3's raw SQL tool and Phase 4's vector search tool follow the same pattern
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 2 status as complete

## Security Considerations

- **This is the phase where the read-only boundary stops being an abstraction and becomes the actual data path for feature code.** `backend/app/agent/tools/db.py` is the only module in `app/agent/` permitted to open a database connection, and every tool built this phase is tested (2.6) to prove it actually goes through that module, not just that the module itself is correctly configured — closing the gap between "the role exists and works" (Phase 0/1) and "the feature code that will eventually be reachable from an LLM's tool calls (Phase 3) actually uses it."
- **The one place this phase selects SQL fragments by argument value** (`get_cohort_comparison()`'s `metric` parameter, 2.5) is handled via a small, hardcoded, exhaustively-tested allow-list dict (`_METRIC_EXPRESSIONS`) with a runtime `ValueError` guard for anything outside it — not string interpolation from caller input. This is the one spot in this phase that could look, at a glance, like it violates CLAUDE.md's "no dynamic table/column names built from LLM output" rule, so it's called out explicitly here and commented in the code itself, rather than left for a future reviewer to have to reconstruct the reasoning for.
- **No new secrets** beyond `READONLY_DB_PASSWORD`, which already existed in `.env`/`.env.example` since Phase 0 (created for migration `0002`) — this phase just adds a typed, fail-fast `Settings` field for it so application code no longer has to reach into `os.environ` directly the way the migration and test fixtures currently do.
- **No new dependencies.** Phase 2 is pure Python + SQLAlchemy `text()`, already present in `pyproject.toml` — nothing to `pip audit` beyond what Phase 0/1 already established as a clean baseline.
- No authentication/authorisation changes — matches master-plan.md §2 (still no user accounts). No new API surface at all this phase (no FastAPI routes) — these are plain importable Python functions, not yet reachable from outside the backend process.

## Testability

No new user roles, scheduled/automated features, or external service integrations are introduced in this phase, so CLAUDE.md's test-account, manual-trigger, and sandbox-mode mechanisms don't apply here in the sense they'd apply to a later phase (e.g. Phase 5's model routing, Phase 7's trickle generator).

This phase's actual testability contribution is the pure/impure split established in 2.2–2.5: every tool's core computation (`_summarize_daily_rows`, `_build_item_velocities`, `_prior_period`/`_compare`, `_ratio`) is a plain function that takes fixture data and returns a dataclass, independently testable without a database connection, an event loop, or seeded data. This is what makes the fast unit-test layer possible at all, and it's the same architectural lesson Phase 1 already established with `generators.py`/`seed.py` — carried forward here rather than reinvented, and worth carrying forward again into Phase 3's raw SQL tool and Phase 4's vector search tool (noted as a documentation update above).

## Dependencies & Risks

- **Halves-split item velocity vs. seed-patterns.md's thirds-based methodology produce different (both real, non-contradictory) ratios.** `seed-patterns.md`'s documented ~3.0x figure for Bella Notte's Truffle Fries trend uses a first-30/last-30-days-with-middle-excluded bucketing; this phase's `get_item_velocity()` tool uses an even halves split for its general-purpose trend field, which the ramp formula predicts should land around ~2.2x instead. Both are real, correctly-computed numbers describing the same underlying pattern at different granularities — not a contradiction — but it's worth stating plainly so a future reader doesn't see "2.2x" in one place and "3.0x" in another and assume a bug. 2.6 mitigates this by testing *both* methodologies explicitly: the tool's own halves-based trend field, and a direct thirds-style comparison (two separate `get_item_velocity()` calls) that reproduces `seed-patterns.md`'s exact bucketing and its exact ~3.0x-class result.
- **Single-day comparisons (`compare_periods()` with a 1-day period) carry more noise than 90-day-aggregated averages.** The generator's ±12% Gaussian noise on daily transaction counts is smoothed out heavily when averaged over dozens of days (per Phase 1's own risk register, "statistical noise could mask a deliberate pattern on an unlucky run" — mitigated there by wide margins), but a single Tuesday-vs-Monday comparison has much less averaging to lean on. 2.6's threshold for that specific test (-25%, vs. an expected ~-50% gap from the generator's own multipliers) is set conservatively for exactly this reason; if it ever flakes in practice despite that margin, the fix is to pick a different, less boundary-adjacent Tuesday in the test rather than lowering the threshold further.
- **No isolated test database, still.** As already true and documented in Phase 1's own plan, this project has no `TEST_DATABASE_URL` — Phase 2's integration tests (via the new `seeded_restaurants` fixture) re-seed the same local Postgres instance `DATABASE_URL` points at. Running `pytest` still resets whatever's currently in that database, exactly as before; no new mechanism is introduced or needed this phase.
- **Docker is not installed in this implementation environment.** As with Phase 0/1, all "run this against the database" tasks in this plan are written generically and were run/verified against the local Homebrew Postgres 17 + pgvector instance rather than a `docker-compose up` stack. No Phase-2-specific risk beyond what Phase 0/1 already flagged — noted here only so the pattern isn't assumed to have silently changed.
- **`app/agent/tools/db.py`'s per-call engine creation is a deliberate trade-off, not an oversight — flagged for the ADR listed above** so it's a documented, defensible choice (and one worth being ready to discuss in an interview context, given this project's stated purpose) rather than something a future reviewer "fixes" into a cached singleton without realising why it wasn't one already.
