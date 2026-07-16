# ADR-004: Seed Data Determinism & Pattern-Injection Methodology

**Date:** 2026-07-15
**Status:** Accepted

## Context

Ask Sous's whole point (master-plan.md §9) is verifiable correctness: the builder must be able to independently confirm, by hand, that the agent's numeric answers are real. That's only possible if the underlying seed data is (a) deterministic — the same every time it's regenerated — and (b) contains patterns deliberate and strong enough to tell apart from noise. Phase 1 is where both properties get built in.

## Decision

### Explicit `rng`/`faker` dependency injection, not global seeding

`backend/app/seed/generators.py` never calls `random.seed()` or `Faker.seed()`. Instead, exactly one `rng = random.Random(FIXED_SEED)` and one `faker = Faker(); faker.seed_instance(FIXED_SEED)` are constructed once (`make_rng_and_faker()`) and passed explicitly into every generator function. This is what makes each generator independently unit-testable without a database or any hidden global state — a test constructs its own `rng`/`faker` pair and calls a generator function directly, with no risk of test-order-dependent pollution from some other test's global seed call.

### Fixed calendar anchor, not `datetime.now()`

`SEED_END_DATE = date(2026, 7, 14)` is a hardcoded constant, and the seeded window is the 90 calendar days ending on it. Using "today" would make re-running the seed script on a different day produce a different transaction-time range, breaking "identical output every run." The tradeoff — seed data doesn't creep forward with real time — is intentional: this is the deterministic historical base; Phase 7's optional live-trickle generator is what makes the demo feel "live," using real timestamps, layered on top later.

### Deterministic UUIDs, drawn from the seeded RNG

Primary keys for generated rows are `uuid.UUID(int=rng.getrandbits(128), version=4)`, not `uuid.uuid4()`. This makes "identical output every run" a literal, byte-for-byte guarantee — including surrogate keys, not just the business figures. **This convention is scoped to `seed.py`/`generators.py` only.** Phase 7's live-trickle generator (`trickle.py`) must generate genuinely random, non-deterministic UUIDs (real `uuid.uuid4()`) and must not reuse `FIXED_SEED` — it exists specifically to simulate ongoing, non-deterministic activity, and inheriting this phase's determinism would defeat that purpose.

### Three deliberate, documented, hand-verifiable patterns

See `docs/reference/seed-patterns.md` for the full write-up, exact constants, verification queries, and actual results. Summary:

1. **Golden Skillet — Tuesday slowdown.** An additional `× 0.45` multiplier applied only on Golden Skillet's Tuesdays. Actual result: ~57.7% below its own weekly average.
2. **Bella Notte — Truffle Fries trending up.** A per-transaction inclusion-probability ramp (5% → 35% across the 90-day window) for one specific menu item. Actual result: ~5.2x more units sold in the last 30 days vs. the first 30.
3. **Sakura Table — premium ticket size.** A structural menu-pricing difference (higher price ranges than the other four restaurants), producing a genuine average-ticket gap. Actual result: ~2.1x the other four restaurants' combined average. This third pattern exists specifically to give Phase 2's peer/cohort comparison tool a real, hand-verifiable structural difference to detect — `implementation-plan.md` names the first two patterns as examples ("e.g."), not an exhaustive list, so adding a third in service of the cohort-comparison tool is within scope, not scope creep.

Each pattern is designed with a large safety margin over its verification threshold specifically so statistical noise (the ±12% Gaussian noise on daily transaction counts) can never plausibly mask it.

### Two control restaurants

Casa Verde and Harbor & Vine receive no deliberate multiplier at all. Without them, "Golden Skillet is slower on Tuesdays" would be unfalsifiable — every restaurant has *some* day-of-week variation from the shared baseline curve alone. The controls are what make the deliberate patterns provably deliberate, not incidental noise that happened to look patterned.

## Consequences

- Easier: every later phase (aggregation tools, agent answers, UI demo) has a fixed, hand-checkable ground truth to verify against — re-running the seed script always reproduces the exact same numbers.
- Easier: generator functions are unit-testable in isolation, fast, and don't need a database.
- Harder: the seed script's business data won't advance with real time on its own — anyone wanting a "live-feeling" demo needs Phase 7's trickle generator layered on top, since Phase 1's data is permanently anchored to July 2026.

## Alternatives Considered

- **Global `random.seed()` / `Faker.seed()` at module import time** — rejected. Works for the seed script itself, but makes the generator functions untestable in isolation (a test would depend on import order / global state rather than being self-contained), and risks silent interference from any other code that also touches the global RNG.
- **`datetime.now()`-anchored seed window** — rejected outright; directly breaks the "identical output every run" requirement that everything else in this ADR depends on.
- **Only two deliberate patterns (matching implementation-plan.md's two named examples exactly)** — considered, but rejected in favor of adding the third (Sakura Table) specifically because Phase 2's implementation plan explicitly calls for a peer/cohort comparison tool, and that tool needs *something* real to detect. Two patterns (revenue summary, item velocity) would leave cohort comparison with nothing to prove against.
