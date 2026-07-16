# Phase 1: Data Layer — Implementation Plan

**Date:** 2026-07-15
**Status:** In Progress
**Source:** implementation-plan.md Phase 1

---

## Goal

Turn the empty schema skeleton from Phase 0 into a fully-modelled, fully-seeded Postgres database: six SQLAlchemy models covering restaurants, menu items, transactions, transaction line items, reviews, and campaigns; one Alembic migration that creates them (including nullable `vector` columns ready for Phase 4's embeddings); and a deterministic, idempotent Faker-based seed script that populates five restaurants with 90 days of realistic, *deliberately patterned* transaction history. The deliberate patterns — one restaurant genuinely slower on Tuesdays, one menu item genuinely trending up in quantity sold, one restaurant genuinely running a higher average ticket size than its peers — are this phase's actual point. Per master-plan.md §9, "verifiable correctness, not breadth or performance" is the project's core success metric, and this phase is where that becomes possible at all: every later phase (aggregation tools, the agent, the frontend) is only as trustworthy as the ground truth it's checked against. `docs/reference/seed-patterns.md`, produced by this phase, is the document the builder will use for the rest of the project to independently verify that the agent never invents a number.

## Prerequisites

- Phase 0 complete: `backend/app/db/base.py` (`Base(DeclarativeBase)`), Alembic initialised under `backend/app/db/migrations/` with migration `0001` (vector extension) and `0002` (`ask_sous_readonly` role, via `ALTER DEFAULT PRIVILEGES`) applied.
- A running local Postgres 16+ instance with the `pgvector` extension available — either via `docker-compose up` (if Docker is available) or a local Homebrew Postgres + pgvector install, per the deviation documented in `docs/changelog.md`'s Phase 0 entry. This plan's "run the migration" / "run the seed script" tasks are written generically and work against either.
- `.env` populated per `.env.example`, including `DATABASE_URL` (admin/migration credentials) and `READONLY_DB_PASSWORD` (consumed by migration `0002`, already applied).
- Backend virtualenv active, Phase 0's dependencies installed (`pip install -e ".[dev]"` from `backend/`).
- No GCP/Vertex AI setup required for this phase — no live model calls happen until Phase 3.

## Implementation Details

### 1.1 Schema

Six SQLAlchemy 2.0 models against the shared `Base` from `backend/app/db/base.py`, in a new `backend/app/db/models.py`. Fields per master-plan.md §3 and the Postgres-terms block in master-plan.md §7, with CLAUDE.md's universal DB conventions applied on top: UUID primary keys, `created_at`/`updated_at` on every table (including `transaction_items`, which master-plan.md §3.4 doesn't list `id`/timestamps for explicitly — CLAUDE.md's "all tables" rule is treated as authoritative here, since it's a project-wide convention, not a per-entity opt-in; deviation is deliberate and should be noted in the ADR, not silently reconciled later), plural snake_case table names (already satisfied by the entity names as given), no soft deletes.

**`TimestampMixin`** (mixed into every model): `created_at: Mapped[datetime]` (`DateTime(timezone=True)`, `server_default=func.now()`), `updated_at: Mapped[datetime]` (same type, `server_default=func.now()`, `onupdate=func.now()`).

**Primary keys:** `id: Mapped[uuid.UUID]` (`UUID(as_uuid=True)`, `primary_key=True`, Python-side `default=uuid.uuid4` — not a server-side `gen_random_uuid()` default, since all inserts in this project go through the ORM/seed script, never raw SQL bypassing it, so a client-side default is simpler and keeps ID generation visible to Python code, which matters for the seed script's determinism requirement below).

**`restaurants`**
- `name: str` (`String(120)`, not null)
- `cuisine: str` (`String(60)`, not null)
- `city: str` (`String(80)`, not null)
- `region: str` (`String(40)`, not null)
- `size_category: str` (`String(20)`, not null, `CheckConstraint("size_category IN ('small','medium','large')")`)
- `brand_voice_guide: str` (`Text`, not null)
- Relationships: `menu_items`, `transactions`, `reviews`, `campaigns` (all `relationship(..., back_populates="restaurant", cascade="all, delete-orphan")` — cascade matters less in practice, since re-seeding truncates rather than deletes, but keeps the model internally consistent with "no soft deletes, real cascading deletes if ever needed").

**`menu_items`**
- `restaurant_id: uuid.UUID` (FK → `restaurants.id`, `ondelete="CASCADE"`, not null, indexed)
- `name: str` (`String(120)`, not null)
- `category: str` (`String(40)`, not null — e.g. `appetizer`, `entree`, `dessert`, `beverage`; no CHECK constraint, since the category set is looser/more descriptive than the other closed-set fields below)
- `price: Decimal` (`Numeric(10, 2)`, not null)

**`transactions`**
- `restaurant_id: uuid.UUID` (FK → `restaurants.id`, `ondelete="CASCADE"`, not null)
- `transaction_time: datetime` (`DateTime(timezone=True)`, not null)
- `total_amount: Decimal` (`Numeric(10, 2)`, not null)
- `payment_type: str` (`String(20)`, not null, `CheckConstraint("payment_type IN ('cash','credit_card','debit_card','mobile_pay')")`)
- `channel: str` (`String(20)`, not null, `CheckConstraint("channel IN ('dine-in','takeout','delivery')")`)
- Composite index `ix_transactions_restaurant_id_transaction_time` on `(restaurant_id, transaction_time)` — this is the access pattern every Phase 2 aggregation tool will use ("this restaurant, this date range"), so it's added now rather than discovered as a missing index later.

**`transaction_items`**
- `transaction_id: uuid.UUID` (FK → `transactions.id`, `ondelete="CASCADE"`, not null, indexed)
- `menu_item_id: uuid.UUID` (FK → `menu_items.id`, `ondelete="RESTRICT"`, not null, indexed — `RESTRICT` rather than `CASCADE`, since a menu item disappearing shouldn't silently delete historical transaction line items; in practice menu items are never deleted in this project, but the constraint documents the intent)
- `quantity: int` (`Integer`, not null, `CheckConstraint("quantity > 0")`)
- `unit_price: Decimal` (`Numeric(10, 2)`, not null — the menu item's price *at the time of the transaction*; in v1 menu prices are static across the whole 90-day seed window, so this will equal the current `menu_items.price`, but the column exists separately to keep transaction history correct if that ever changes)

**`reviews`**
- `restaurant_id: uuid.UUID` (FK → `restaurants.id`, `ondelete="CASCADE"`, not null, indexed)
- `rating: int` (`SmallInteger`, not null, `CheckConstraint("rating BETWEEN 1 AND 5")`)
- `review_text: str` (`Text`, not null)
- `source: str` (`String(20)`, not null, `CheckConstraint("source IN ('google','yelp','walk_in','in_app')")`)
- `created_at` — master-plan.md §3.5 lists this explicitly as one of `reviews`' own fields (the review's post date), which happens to coincide with CLAUDE.md's universal `created_at` convention; no conflict, one column serves both purposes.
- `embedding: list[float] | None` (`pgvector.sqlalchemy.Vector(768)`, **nullable**, no default) — populated in Phase 4; see ADR-003 for the dimensionality choice.

**`campaigns`**
- `restaurant_id: uuid.UUID` (FK → `restaurants.id`, `ondelete="CASCADE"`, not null, indexed)
- `name: str` (`String(120)`, not null)
- `channel: str` (`String(20)`, not null, `CheckConstraint("channel IN ('sms','email','social')")`)
- `sent_at: datetime | None` (`DateTime(timezone=True)`, **nullable** — seeded historical campaigns get a `sent_at` within the 90-day window; nothing in v1 ever creates a campaign without one, but the column stays nullable since master-plan.md §4.3 describes drafts that are "never actually sent")
- `copy_text: str` (`Text`, not null)
- `conversion_rate: Decimal | None` (`Numeric(5, 4)`, nullable — fraction, e.g. `0.0842` = 8.42%)
- `revenue_lift: Decimal | None` (`Numeric(10, 2)`, nullable — dollar figure; master-plan.md doesn't specify units, dollars is the documented assumption)
- `embedding: list[float] | None` (`pgvector.sqlalchemy.Vector(768)`, **nullable** — on `copy_text`, populated in Phase 4 for few-shot retrieval; see ADR-003)

**Deliberately out of scope for this phase:** a pgvector ANN index (`ivfflat`/`hnsw`) on either `embedding` column. Building a similarity index over an entirely-`NULL` column is meaningless (`ivfflat` indexes are trained on existing vectors), so index creation is Phase 4's job, once embeddings actually exist. Noted here so it isn't silently forgotten.

**Migration:** one new Alembic revision, generated via `alembic revision --autogenerate -m "create_core_schema"` (down-revision will be `ae93ecc2fa1c`, Phase 0's readonly-role migration — Alembic assigns the actual new revision hash at generation time). Autogenerate is a starting point, not the final file — known gotchas to check by hand before applying:
- `pgvector.sqlalchemy.Vector` needs its import (`from pgvector.sqlalchemy import Vector`) added to the migration file; autogenerate sometimes omits custom-type imports.
- `CheckConstraint`s and the composite index on `transactions` need to be present and correctly named (convention: `ck_<table>_<column_or_name>`, `ix_<table>_<column(s)>`) — autogenerate output should be diffed against the model definitions above, not applied blindly.
- Table creation order in the migration must satisfy FK dependencies (`restaurants` → `menu_items`/`transactions`/`reviews`/`campaigns` → `transaction_items`); downgrade drops in the reverse order: `transaction_items`, `transactions`, `reviews`, `campaigns`, `menu_items`, `restaurants`.

**Critical dependency on ADR-002 (Phase 0):** this migration must run under the same admin `DATABASE_URL` credentials as migrations `0001`/`0002` did — which it will, by construction, since it's just the next `alembic upgrade head` step. This is what makes `ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES TO ask_sous_readonly` (already applied in `0002`) automatically cover all six new tables with zero additional grant statements. This phase adds an explicit test proving that held true (see Tasks below) rather than assuming it.

**Tasks (red-green-refactor):**
- [ ] Add `pgvector` (the Python package providing `pgvector.sqlalchemy.Vector`) to `backend/pyproject.toml`'s runtime `dependencies`
- [ ] Write a failing integration test (`backend/tests/integration/test_schema_migration.py`) asserting, after `alembic upgrade head`, all six expected tables exist (query `information_schema.tables`), and spot-checking key columns via `information_schema.columns`: UUID type on every `id`/`*_id` FK column, `numeric` type on `price`/`total_amount`/`unit_price`/`conversion_rate`/`revenue_lift`, `USER-DEFINED` type with `udt_name = 'vector'` and `is_nullable = 'YES'` on `reviews.embedding` and `campaigns.embedding`
- [ ] Write a failing integration test in the same file asserting a smoke insert of one row per table (via the ORM, using an `AsyncSession` against `Base.metadata`-backed models) succeeds in dependency order, and that an FK violation is actually enforced (inserting a `menu_items` row with a random, non-existent `restaurant_id` raises `IntegrityError`)
- [ ] Write a failing integration test (extend `backend/tests/integration/test_db_bootstrap.py` or add to `test_schema_migration.py`) parametrized over all six table names, asserting the `ask_sous_readonly` role (via the existing `readonly_engine` fixture from `backend/tests/integration/conftest.py`) can `SELECT` from each one (even zero rows) with no explicit grant beyond what `0002`'s `ALTER DEFAULT PRIVILEGES` already provides, and that it is rejected (`InsufficientPrivilege`) on `INSERT INTO restaurants ...`
- [ ] Implement `backend/app/db/models.py`: `TimestampMixin` and all six models exactly as specified above, importing `Base` from `app/db/base.py`
- [ ] Generate and hand-correct the migration (`alembic revision --autogenerate -m "create_core_schema"`), applying the known-gotcha fixes listed above
- [ ] Run `alembic upgrade head` against the local Postgres instance; confirm all three tests above pass
- [ ] Refactor: confirm constraint/index names follow the `ck_<table>_<name>` / `ix_<table>_<column(s)>` convention consistently across all six tables, and that no model re-derives `Base` instead of importing the shared one

### 1.2 Seed script

`backend/app/seed/generators.py` (pure, DB-free statistical generators) and `backend/app/seed/seed.py` (thin orchestration: truncate, generate, bulk-insert, summarize) — matching the split CLAUDE.md's Project Structure already names for this directory. `Faker` is added as a runtime dependency (already listed in `stack.md`).

**Determinism, precisely:** no code in this phase calls the global `random.seed()` / `Faker.seed()`. Instead, `seed.py`'s orchestrator constructs exactly one `rng = random.Random(FIXED_SEED)` and one `faker = Faker(); faker.seed_instance(FIXED_SEED)` (constant `FIXED_SEED = 42`, defined once in `generators.py`), and passes both explicitly into every generator function. This dependency-injection style (rather than global seeding) is what makes the generators independently unit-testable without a database or any hidden global state — a test constructs its own `rng`/`faker` instances and calls a generator function directly. Primary key UUIDs are also generated *from* this same `rng` (`uuid.UUID(int=rng.getrandbits(128), version=4)`), not `uuid.uuid4()` — this is what makes "identical output every run" a literal, byte-for-byte guarantee (including surrogate keys), not just "the same business figures." This convention is scoped to `seed.py`/`generators.py` only — Phase 7's live-trickle generator (`trickle.py`) must **not** reuse deterministic UUIDs or a fixed RNG seed, since it's explicitly meant to simulate non-deterministic ongoing activity; call this out in the ADR so it isn't "fixed" into `trickle.py` later by someone assuming project-wide consistency.

**Fixed calendar anchor:** `SEED_END_DATE = date(2026, 7, 14)` (constant in `generators.py`), with the seeded window being the 90 calendar days `[SEED_END_DATE - timedelta(days=89), SEED_END_DATE]` inclusive. This is a fixed date, not `datetime.now()` — using "today" would make re-running the seed script on a different day produce a different transaction-time range, breaking "identical output every run." The trade-off (seed data doesn't creep forward with real time) is intentional: Phase 1's seed is the deterministic historical base; Phase 7's optional trickle generator is what makes the demo feel "live" using real timestamps, layered on top later.

**Five restaurant profiles** (hardcoded identities in `RESTAURANT_PROFILES`, not Faker-randomized — the *identities* are fixed and memorable on purpose, so the deliberate patterns can be described by name in `seed-patterns.md` and referenced consistently across every later phase; only the transactional data *within* each restaurant is randomly generated):

| Restaurant | Cuisine | City / Region | Size | Deliberate pattern |
|---|---|---|---|---|
| Golden Skillet | American comfort food | Austin, TX / South | medium | Tuesday slowdown |
| Bella Notte | Italian | Chicago, IL / Midwest | medium | Truffle Fries trending up |
| Sakura Table | Japanese | Seattle, WA / West | large | Premium ticket size (cohort outlier) |
| Casa Verde | Mexican | Austin, TX / South | small | None — control |
| Harbor & Vine | Seafood & wine bar | Portland, OR / West | medium | None — control |

Each profile includes a short, distinct `brand_voice_guide` string (e.g. Golden Skillet: warm, down-to-earth, comfort-food language; Sakura Table: refined, minimalist, precision-and-craft language; Casa Verde: playful, vibrant, family-friendly) — exact wording is the implementer's call, but each must read as clearly distinguishable from the others, since Phase 5's campaign generation grounds copy in this text.

**Menu items:** 10–14 per restaurant via `generate_menu_items()`, spanning `appetizer`/`entree`/`dessert`/`beverage` categories, drawn from a small curated in-code pool of realistic food-item name templates per cuisine (Faker has no reliable food/menu provider, so a hand-written pool — not `faker.word()` — is used for name realism; `Faker` is still used for review text and campaign-copy filler prose). Bella Notte's pool must include an item literally named **"Truffle Fries"** (the anchor item for its trend pattern). Prices are drawn per-category from a `rng.uniform(low, high)` range that differs for Sakura Table vs. the other four restaurants (the mechanism behind the premium-ticket pattern, below).

**Baseline transaction-volume distribution (shared across all five restaurants, before any deliberate override):**
- Base mean daily transaction count by `size_category`: small = 45, medium = 75, large = 115.
- Day-of-week multiplier (Mon–Sun): `{Mon: 0.90, Tue: 1.00, Wed: 0.95, Thu: 1.00, Fri: 1.25, Sat: 1.35, Sun: 1.10}`.
- Hourly weight distribution for allocating a day's transactions across the clock: `11:00–13:59` weight 3.0 (lunch), `14:00–16:59` weight 0.6 (afternoon lull), `17:00–20:59` weight 4.0 (dinner), `21:00–22:59` weight 1.0 (late), all other hours weight 0 (closed) — allocated via `rng.choices(hours, weights=...)`.
- Actual daily transaction count is drawn as `max(1, round(rng.gauss(expected_count, expected_count * 0.12)))`, where `expected_count = base_count[size] * day_of_week_multiplier[weekday] * deliberate_multiplier(restaurant, date)`.
- Per transaction: 1–4 distinct line items (`rng.randint(1, 4)`), quantity per line item `rng.choices([1, 2, 3], weights=[60, 30, 10])`, `channel` weighted `{dine-in: 0.55, takeout: 0.30, delivery: 0.15}`, `payment_type` weighted `{credit_card: 0.55, debit_card: 0.20, mobile_pay: 0.20, cash: 0.05}`. `total_amount` is **computed**, not independently randomised — it is always `sum(quantity * unit_price)` over that transaction's generated line items, enforced as an invariant (see tests below), so downstream aggregation-tool correctness checks can trust that `transactions.total_amount` and `transaction_items` never disagree.

**Deliberate pattern 1 — Golden Skillet, Tuesday slowdown:** on top of the shared `Tue: 1.00` baseline multiplier, Golden Skillet gets an additional `× 0.45` `deliberate_multiplier` applied only on Tuesdays across the full 90-day window. Effective Tuesday multiplier ≈ 0.45 vs. Golden Skillet's own ≈1.09 average across its other six days — Tuesday revenue lands roughly 59% below its own weekly-day average, comfortably clearing the "at least 20% below" bar named in implementation-plan.md with margin to spare against the ±12% Gaussian noise on daily counts.

**Deliberate pattern 2 — Bella Notte, Truffle Fries trending up:** for every transaction generated at Bella Notte, after its normal random line-item selection, roll an independent inclusion check for Truffle Fries with probability `p(day_index) = 0.05 + 0.30 * (day_index / 89)`, where `day_index` is the 0-based offset of that transaction's date within the 90-day window (0 = `SEED_END_DATE - 89`, 89 = `SEED_END_DATE`). This produces a probability ramp from 5% at the start of the window to 35% at the end (a ~7x rise in daily inclusion odds), which — averaged over each 30-day third — yields roughly a 3x rise in total quantity sold between the first and last 30-day windows, well clear of the "at least 2x" bar.

**Deliberate pattern 3 — Sakura Table, premium ticket size (cohort/peer comparison):** not a runtime probability effect but a structural one, baked into menu pricing at generation time. Sakura Table's `generate_menu_items()` draws prices from `entree: rng.uniform(24, 46)`, `appetizer: rng.uniform(12, 22)`, `dessert: rng.uniform(9, 14)`, `beverage: rng.uniform(6, 16)`; the other four restaurants draw from `entree: rng.uniform(11, 22)`, `appetizer: rng.uniform(6, 12)`, `dessert: rng.uniform(5, 9)`, `beverage: rng.uniform(3, 9)`. Because `total_amount` is always computed from real line items at real prices, this produces a genuine, consistent gap in average transaction size — Sakura Table's average `total_amount` across the 90 days should land at roughly double the other four restaurants' combined average, comfortably clearing a "1.3x" verification bar. This third pattern is an addition beyond the two examples implementation-plan.md names explicitly (both of which are introduced with "e.g.", not as an exhaustive list) — it exists specifically to give Phase 2's peer/cohort comparison tool a genuine, hand-verifiable structural difference to detect, the same way the other two patterns exist for the revenue-summary and item-velocity tools respectively.

Casa Verde and Harbor & Vine receive **no deliberate multiplier at all** — they exist as controls, so that verifying "Golden Skillet is different" or "Sakura Table is different" means something (a real deviation from an otherwise-shared baseline), not just generic randomness that happens to look patterned.

**Reviews:** 20–40 per restaurant, spread across the 90-day window, `rating` drawn via `rng.choices([1,2,3,4,5], weights=[2,3,10,35,50])` (realistically skewed positive), `review_text` a short Faker-assisted sentence/paragraph, `source` weighted across `google`/`yelp`/`walk_in`/`in_app`. No deliberate statistical pattern required here — Phase 4 uses these for qualitative vector search, not numeric aggregation, so "plausible and present" is sufficient; unit tests below only check shape (non-empty text, rating in range, correct count).

**Campaigns:** 3–5 past campaigns per restaurant, `sent_at` randomly placed within the 90-day window, `channel` weighted across `sms`/`email`/`social`, `copy_text` generated from a small set of hand-written templates per restaurant (referencing the restaurant's name/cuisine/brand voice, filled in with `faker`-assisted specifics for variety) — copy quality doesn't need to be good prose yet (no LLM involved until Phase 3+), it just needs to exist and be plausibly on-brand so Phase 5's few-shot retrieval has real examples to pull from. `conversion_rate` drawn `rng.uniform(0.01, 0.15)`, `revenue_lift` drawn `rng.uniform(50, 3000)`.

**Data volume & performance:** approximate scale is 5 restaurants × 90 days × ~45–115 transactions/day ≈ 28,000–36,000 transactions, and roughly 1.5–2x that in `transaction_items` rows (≈45,000–70,000). Per-row ORM `session.add()` + individual flushes at this volume would be slow; `seed_database()` must build plain dicts via the generator functions and bulk-insert them with SQLAlchemy Core (`insert(Model.__table__).values(rows)` executed once per table, or in batched chunks) rather than constructing and flushing thousands of individual ORM objects.

**`seed.py` structure:**
- `async def seed_database(session: AsyncSession) -> dict[str, int]`: truncates all six tables in one statement (`TRUNCATE TABLE transaction_items, transactions, reviews, campaigns, menu_items, restaurants RESTART IDENTITY CASCADE`, order-independent thanks to `CASCADE`), builds the `rng`/`faker` pair from `FIXED_SEED`, calls the `generators.py` functions in dependency order (restaurants → menu items → transactions/transaction_items → reviews → campaigns), bulk-inserts each set, and returns a `{"restaurants": 5, "menu_items": N, ...}` row-count summary.
- `async def main() -> None`: loads settings, opens a session against the admin `DATABASE_URL` (reusing `app.db.session.async_session_maker`), calls `seed_database()`, and prints the summary — this is what `python -m app.seed.seed` runs, per `CLAUDE.md`'s Development Commands.
- `seed.py` itself contains **no** statistical/pattern logic — that all lives in `generators.py`, so it stays testable without a database.

**Tasks (red-green-refactor):**
- [ ] Add `Faker` to `backend/pyproject.toml`'s runtime `dependencies`
- [ ] Write failing unit tests (`backend/tests/unit/test_seed_generators.py`), calling `generators.py` functions directly with explicitly-constructed `rng`/`faker` instances, no database involved:
  - Determinism: two independent calls with freshly-constructed, identically-seeded `rng`/`faker` instances produce byte-identical output (including generated UUIDs) for every generator function
  - The 90-day window is exactly `[SEED_END_DATE - 89 days, SEED_END_DATE]` inclusive, for every restaurant's generated transactions
  - Golden Skillet: average Tuesday revenue is at least 30% below its all-week daily average (asserted with margin below the designed ~59% gap, to tolerate Gaussian noise without a flaky test)
  - Casa Verde (control): Tuesday average revenue is within ±20% of its all-week average — proves the suppression pattern is restaurant-specific, not a shared-baseline artifact
  - Bella Notte: total Truffle Fries quantity sold in the last 30 days of the window is at least 2x the first 30 days
  - Sakura Table: average transaction `total_amount` is at least 1.3x the combined average of the other four restaurants' `total_amount`
  - Invariant: for every generated transaction, `total_amount == sum(quantity * unit_price for its transaction_items)` (compare as `Decimal`, no floating-point tolerance needed since both sides are computed from the same `Decimal` inputs)
- [ ] Implement `backend/app/seed/generators.py`: `FIXED_SEED`, `SEED_END_DATE`, `RESTAURANT_PROFILES`, the shared day-of-week/hourly baseline tables, `generate_menu_items()`, `generate_transactions_and_items()` (implementing the three deliberate multipliers exactly as specified above), `generate_reviews()`, `generate_campaigns()` — all pure functions taking explicit `rng`/`faker` arguments — to make the above tests pass
- [ ] Implement `backend/app/seed/seed.py`: `seed_database()` and `main()` as specified above, with bulk Core-level inserts (not per-row ORM flushes) for `transactions`/`transaction_items`
- [ ] Write a failing integration test (`backend/tests/integration/test_seed_integration.py`) asserting, after calling `seed_database()` against the real (local) database: exactly 5 rows in `restaurants`; every restaurant has ≥8 `menu_items`; total `transactions` across all restaurants falls within the expected range implied by the baseline math (document the exact computed range, e.g. ~28,000–36,000, in the test as a comment); every restaurant has at least one transaction on every one of the 90 seeded calendar days (no dead days — query `COUNT(DISTINCT transaction_time::date)` per restaurant); every restaurant has ≥1 review and ≥1 campaign
- [ ] Write a failing integration test asserting `seed_database()` is idempotent: run it twice in a row against the same database, assert identical row counts both times, and assert a specific, deterministic lookup (Golden Skillet's total 90-day revenue via `SELECT SUM(total_amount)`) is byte-identical (`Decimal`-equal) across both runs
- [ ] Write failing integration tests asserting each of the three deliberate patterns is detectable via **direct SQL** against the seeded database (not the generator's in-memory output — proving the pattern survives the DB round-trip):
  - Golden Skillet: `SELECT EXTRACT(DOW FROM transaction_time) AS dow, AVG(total_amount) FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id WHERE r.name = 'Golden Skillet' GROUP BY dow` (or an equivalent daily-revenue-sum-then-average query) shows Tuesday (`dow = 2`) at least 20% below the all-week average
  - Bella Notte: a query joining `transaction_items` → `menu_items` → `transactions`, filtered to Truffle Fries at Bella Notte, summing `quantity` for the first vs. last 30-day sub-windows, shows the last 30 days at least 2x the first
  - Sakura Table: `AVG(total_amount)` for Sakura Table vs. the combined `AVG(total_amount)` of the other four restaurants shows Sakura Table at least 1.3x higher
- [ ] Fix any `seed.py`/`generators.py` issues surfaced by the DB round-trip (e.g. `Decimal` precision/rounding mismatches between Python-computed and Postgres-stored `numeric(10,2)` values) to make the integration tests pass
- [ ] Write `docs/reference/seed-patterns.md`: for each of the 5 restaurants, its profile (name, cuisine, city/region, size, deliberate pattern or "control"); for each of the 3 deliberate patterns, the restaurant/item involved, the exact mechanism and constants (multiplier values, the probability ramp formula), the exact SQL query to independently verify it by hand, and the expected result/threshold with a short worked example of the numbers. This is the reference every later phase (2 onward) uses to sanity-check aggregation-tool output and, eventually, agent answers, against known ground truth
- [ ] Refactor: confirm `seed.py` contains only orchestration (truncate, call generators, bulk-insert, summarize/print) with zero statistical logic, and that every constant named above (`FIXED_SEED`, `SEED_END_DATE`, the multiplier tables, the three pattern constants) is defined exactly once in `generators.py` and imported everywhere else that needs it (tests, `seed-patterns.md`'s worked examples should reference the same numbers, not hand-copy them)

## Testing

The red-green-refactor cycle is embedded in each sub-section's tasks above. This section covers cross-cutting and integration-level verification not tied to a single sub-section. Testing depth for this phase is held to the **stricter bar** CLAUDE.md and implementation-plan.md set for Phase 1/2 specifically, since data-layer correctness is the project's core success metric (master-plan.md §9) — every deliberate pattern gets both a DB-free unit test and a real-Postgres integration test, not just a smoke check.

### Integration Tests
- [ ] Full pipeline test: fresh `alembic upgrade head` followed immediately by `seed_database()` against the same database, asserting no errors and that all of the row-count and deliberate-pattern SQL assertions above pass in one clean, ordered run — proves the migration and the seed script actually compose correctly end-to-end, not just independently
- [ ] Confirm `ask_sous_readonly` can read seeded (non-empty) data end-to-end: after seeding, connect as `ask_sous_readonly` and run a representative aggregate query (e.g. `SELECT COUNT(*) FROM transactions WHERE restaurant_id = :id`) against real rows, not just an empty table — this is the exact read path Phase 2's aggregation tools depend on

### Manual Verification
- [ ] `cd backend && alembic upgrade head` against the local Postgres instance — confirm no errors; run it a second time to confirm idempotency (no-op)
- [ ] `cd backend && python -m app.seed.seed` — confirm the printed summary reports 5 restaurants and non-zero counts for every table; run it a second time and confirm the printed counts are identical
- [ ] Connect via `psql` (or a GUI client such as TablePlus/pgAdmin) and run each of the three exact SQL queries documented in `docs/reference/seed-patterns.md`; confirm the results match the documented expected thresholds
- [ ] Connect via `psql` as `ask_sous_readonly` (credentials from `.env`) and confirm `SELECT * FROM restaurants LIMIT 1;` returns a real row, while `INSERT INTO restaurants (name) VALUES ('test');` is rejected with a permissions error
- [ ] `cd backend && ruff check . && ruff format --check .` — confirm no errors
- [ ] `cd backend && pytest` — confirm all suites (Phase 0's + this phase's new unit/integration tests) pass

## User Acceptance Tests

UAT scenarios for this phase, to be added to `docs/uat.md`. Phase 1 has no user-facing UI yet, so these are framed as exact, followable steps against a database client rather than a browser — matching the precedent set by Phase 0's UAT-0.1 (which also involved running commands and inspecting raw output rather than a polished screen).

- [ ] UAT-1.1: Database seeds successfully with realistic data — With the backend environment set up and migrations applied, run `cd backend && python -m app.seed.seed` from a terminal. Expected: the terminal prints a summary showing 5 restaurants and non-zero counts for menu items, transactions, transaction items, reviews, and campaigns.
- [ ] UAT-1.2: One restaurant is genuinely slower on Tuesdays — Open a Postgres client (`psql`, TablePlus, pgAdmin, etc.) connected to the local database and run the exact query documented under "Golden Skillet — Tuesday slowdown" in `docs/reference/seed-patterns.md`. Expected: Golden Skillet's average Tuesday revenue is meaningfully lower (the documented threshold, at least ~20%, typically much more) than its average revenue on other days of the week.
- [ ] UAT-1.3: One menu item is genuinely trending upward — Run the query documented under "Bella Notte — Truffle Fries trend" in `docs/reference/seed-patterns.md`. Expected: the total quantity of Truffle Fries sold in the most recent 30 days of the seeded window is at least double the quantity sold in the first 30 days.
- [ ] UAT-1.4: Re-running the seed script is safe and repeatable — Immediately after UAT-1.1, run `python -m app.seed.seed` a second time. Expected: the printed summary reports the exact same row counts as the first run, and re-running the query from UAT-1.2 gives the identical numeric result both times — not just "still slower," the same number.

## Documentation Updates

- [ ] Update `docs/tasks.md` with Phase 1 tasks
- [ ] Update `docs/uat.md` with UAT-1.1 through UAT-1.4
- [ ] Update `docs/changelog.md` with a Phase 1 completion summary
- [ ] Write `docs/decisions/003-vector-column-dimensionality.md` (ADR) — see Dependencies & Risks below for the decision content to record
- [ ] Write `docs/decisions/004-seed-data-determinism-and-patterns.md` (ADR) documenting: the explicit `rng`/`faker` dependency-injection approach (vs. global seeding) and why it matters for unit-testability; the fixed calendar anchor (`SEED_END_DATE`) vs. `datetime.now()`; deterministic UUID generation from the seeded RNG and its explicit scoping to `seed.py`/`generators.py` only (not `trickle.py`, Phase 7); the three deliberate patterns and their exact constants; and the inclusion of two "control" restaurants (Casa Verde, Harbor & Vine) as the mechanism that makes the patterns provably deliberate rather than incidental noise
- [ ] Update `CLAUDE.md`: add `docs/reference/seed-patterns.md` to the Key Files list; note the CHECK-constraint-over-native-ENUM convention for closed-set string columns (`size_category`, `payment_type`, `channel`, `source`, `rating`) under Database conventions, so later phases follow the same pattern instead of introducing native Postgres ENUMs; note the seed script's deterministic-UUID-from-seeded-RNG convention and its explicit non-applicability to Phase 7's trickle generator
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 1 status as complete

## Security Considerations

- **Read-only boundary extended, and tested, not assumed.** The dedicated `ask_sous_readonly` role (Phase 0, ADR-002) automatically gains `SELECT` on all six new tables via the `ALTER DEFAULT PRIVILEGES` statement already applied in migration `0002` — but this phase adds an explicit parametrized test (1.1) proving that's actually true for every one of the six tables, plus a rejected-write check, rather than trusting it by inference. This matters because Phase 2 onward connects the agent's tools exclusively through this role against real seeded data for the first time.
- **No new secrets.** This phase adds no new environment variables or credentials — the seed script reuses the same admin `DATABASE_URL` that migrations already use, per CLAUDE.md ("seed/setup scripts... read-write... using separate credentials" from the agent's read-only role, not from migrations, which the seed script already satisfies by construction).
- **No real PII.** `reviews`/`campaigns` contain only fabricated `review_text`/`copy_text` (Faker-assisted or templated) and numeric fields — the schema has no reviewer name/email/contact field at all (per master-plan.md §3.5), so there's no real-or-fake-personal-data surface to worry about beyond "this text is obviously synthetic," which is the intended demo posture.
- **Defense-in-depth via CHECK constraints.** Closed-set string columns (`size_category`, `payment_type`, `channel`, `source`) and the `rating`/`quantity` numeric ranges get database-level `CheckConstraint`s, not just application-level validation — this means even a future direct-SQL bug elsewhere in the codebase can't silently write garbage values into these columns.
- **New dependencies:** `pgvector` (Python package) and `Faker`, both mainstream and actively maintained. Run `pip audit` after adding them, to keep the clean baseline Phase 0 established.
- No authentication/authorisation changes — matches master-plan.md §2 (still no user accounts).

## Testability

No new user roles, automated/scheduled features, or external service integrations are introduced in this phase, so none of CLAUDE.md's testability mechanisms (test-account seeding, manual trigger endpoints, sandbox API modes) apply here in the sense they'd apply to a later phase.

This phase's actual testability contribution is the seed script itself: an idempotent, deterministic, one-command way (`python -m app.seed.seed`) to reset the database to a known, hand-verifiable state. That *is* the testability mechanism every later phase depends on — Phase 2's aggregation-tool tests, Phase 3's agent-answer spot-checks, and Phase 6's UI demo all lean on being able to re-seed and get back to exactly the same ground truth every time. No additional mechanism is needed beyond what this phase already builds.

## Dependencies & Risks

- **Statistical noise could mask a deliberate pattern on an unlucky run.** Mitigated by designing each pattern with a large safety margin over its verification threshold (Tuesday suppression targets ~59% below average against a 20% bar; the trending item targets ~3x against a 2x bar; the premium-ticket gap targets ~2x against a 1.3x bar) and by keeping the daily-count noise band (±12% Gaussian) small relative to those margins. If a test still flakes in practice, the fix is to widen the margin further or reduce the noise band — not to lower the assertion threshold.
- **`pgvector`'s SQLAlchemy `Vector` type and Alembic autogenerate.** Autogenerate sometimes fails to emit the custom-type import for third-party column types; this plan calls out the exact fix (add `from pgvector.sqlalchemy import Vector` by hand) as a known step rather than something to debug fresh, but it's still worth verifying the generated migration file by eye before applying it, per this project's existing "review before applying" convention for all Alembic migrations.
- **Vector dimensionality (768) is chosen ahead of Phase 4's actual embedding model decision.** If Phase 4 ends up selecting a model whose native output dimension differs from 768, a follow-up migration (`ALTER COLUMN embedding TYPE vector(N)`) will be needed — low-impact, since both embedding columns are nullable and entirely empty until Phase 4 populates them. Recorded as ADR-003 so the reasoning (768 chosen because it matches `text-embedding-004`, the most likely default per `stack.md`'s open TBD note, with `gemini-embedding-001` as a fallback that can also be truncated to 768 via its `output_dimensionality` parameter) isn't re-litigated from scratch in Phase 4.
- **No isolated test database.** Phase 0 didn't introduce a `TEST_DATABASE_URL` or equivalent — its own integration tests already create/drop throwaway tables against whatever `DATABASE_URL` points to, and this phase's integration tests follow the same pattern, including a `TRUNCATE` of all application tables. This means running `pytest` resets seed data in whichever Postgres instance `DATABASE_URL` points to. This mirrors Phase 0's existing approach exactly and introduces no new mechanism, but it's worth stating plainly: don't run the test suite against a database whose current seeded state you want to preserve un-reset, and expect to re-run `python -m app.seed.seed` afterward if you want the dev database populated again for manual poking. Introducing a genuinely separate test database is a bigger decision than this phase's scope and isn't proposed here.
- **Seed volume (~30–40k transaction rows) requires bulk inserts, not ORM per-row flushes.** Called out explicitly as an implementation requirement (1.2) rather than left to be discovered as a slow-test problem later.
