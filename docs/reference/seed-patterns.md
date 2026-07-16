# Seed Data Reference

This is the ground truth for Ask Sous's seeded demo data. Every later phase — aggregation tools (Phase 2), the agent's answers (Phase 3+), the frontend demo (Phase 6) — should be checkable against the numbers on this page. If the agent (or a tool) ever reports something that contradicts this document, that's a grounding bug, not a data problem.

Regenerate this data any time with:

```bash
cd backend && python -m app.seed.seed
```

Deterministic and idempotent — running it again always produces the exact same numbers (see `docs/decisions/004-seed-data-determinism-and-patterns.md`).

## Restaurant Profiles

| Restaurant | Cuisine | City / Region | Size | Deliberate pattern |
|---|---|---|---|---|
| Golden Skillet | American comfort food | Austin, TX / South | medium | Tuesday slowdown |
| Bella Notte | Italian | Chicago, IL / Midwest | medium | Truffle Fries trending up |
| Sakura Table | Japanese | Seattle, WA / West | large | Premium ticket size (cohort outlier) |
| Casa Verde | Mexican | Austin, TX / South | small | None — control |
| Harbor & Vine | Seafood & wine bar | Portland, OR / West | medium | None — control |

Seed window: 90 calendar days ending **2026-07-14** (fixed `SEED_END_DATE`, not "today" — see ADR-004).

Actual seeded row counts (from the most recent `python -m app.seed.seed` run): 5 restaurants, 59 menu items, 37,019 transactions, 94,113 transaction items, 142 reviews, 17 campaigns. These non-transaction-and-review-adjacent counts (menu items, restaurants) stay fixed across code changes; the exact transaction/review/campaign counts can shift slightly whenever generator code changes the number of `rng` draws consumed earlier in the fixed generation sequence (menu items → transactions → reviews → campaigns, per restaurant) — expected and harmless given the single shared `random.Random` stream ADR-004 describes, not a sign of broken determinism (the same code + same `FIXED_SEED` still always produces the same output).

---

## Pattern 1 — Golden Skillet: Tuesday slowdown

**Mechanism:** on top of the shared day-of-week baseline multiplier (Tuesday = 1.00, same as Thursday), Golden Skillet gets an additional `× 0.45` multiplier applied only on Tuesdays across the full 90-day window (`GOLDEN_SKILLET_TUESDAY_MULTIPLIER` in `backend/app/seed/generators.py`).

**Verify by hand:**

```sql
SELECT EXTRACT(DOW FROM transaction_time)::int AS dow, ROUND(AVG(daily_total), 2) AS avg_daily_revenue
FROM (
  SELECT transaction_time::date AS d, SUM(total_amount) AS daily_total
  FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id
  WHERE r.name = 'Golden Skillet'
  GROUP BY transaction_time::date
) daily
JOIN transactions t2 ON t2.transaction_time::date = daily.d
GROUP BY dow ORDER BY dow;
```

(Postgres `EXTRACT(DOW ...)`: Sunday=0 ... Saturday=6, so Tuesday = 2.)

**Actual result (most recent seed run):**

| dow | avg_daily_revenue |
|---|---|
| 0 (Sun) | $3,296.66 |
| 1 (Mon) | $2,710.83 |
| **2 (Tue)** | **$1,354.40** |
| 3 (Wed) | $2,723.32 |
| 4 (Thu) | $2,949.22 |
| 5 (Fri) | $3,783.32 |
| 6 (Sat) | $3,758.04 |

Average of the other six days: $3,203.57. Tuesday ($1,354.40) is **~57.7% below** that average — comfortably clears the "at least 20% below" bar named in `implementation-plan.md`.

**Control check:** Casa Verde (no deliberate pattern) shows Tuesday within ±20% of its own weekly average — proving Golden Skillet's suppression is restaurant-specific, not a shared-baseline artifact.

---

## Pattern 2 — Bella Notte: Truffle Fries trending up

**Mechanism:** for every transaction generated at Bella Notte, after normal line-item selection, an independent inclusion check for Truffle Fries is rolled with probability `p(day_index) = 0.05 + 0.30 * (day_index / 89)` — a ramp from 5% at the start of the 90-day window to 35% at the end (`TRUFFLE_FRIES_P_START` / `TRUFFLE_FRIES_P_SLOPE` in `generators.py`).

**Verify by hand:**

```sql
-- Symmetric first-30 / last-30 buckets (the 90-day window's middle 30 days
-- are deliberately excluded, not lumped into "last_30").
SELECT bucket, SUM(qty) FROM (
  SELECT ti.quantity AS qty,
    CASE
      WHEN t.transaction_time::date <= (
        SELECT MIN(transaction_time::date) + 29 FROM transactions tt
        JOIN restaurants rr ON rr.id = tt.restaurant_id WHERE rr.name = 'Bella Notte'
      ) THEN 'first_30'
      WHEN t.transaction_time::date >= (
        SELECT MAX(transaction_time::date) - 29 FROM transactions tt
        JOIN restaurants rr ON rr.id = tt.restaurant_id WHERE rr.name = 'Bella Notte'
      ) THEN 'last_30'
      ELSE NULL
    END AS bucket
  FROM transaction_items ti
  JOIN transactions t ON t.id = ti.transaction_id
  JOIN restaurants r ON r.id = t.restaurant_id
  JOIN menu_items m ON m.id = ti.menu_item_id
  WHERE r.name = 'Bella Notte' AND m.name = 'Truffle Fries'
) bucketed
WHERE bucket IS NOT NULL
GROUP BY bucket;
```

**Actual result:** first 30 days = 363 units sold, last 30 days = 1,096 units sold — a **~3.0x increase**, clearing the "at least 2x" bar and matching the ramp formula's own prediction (see `generators.py`'s docstring: "~3x rise... averaged over each 30-day third").

---

## Pattern 3 — Sakura Table: premium ticket size (cohort/peer comparison)

**Mechanism:** not a runtime probability effect but a structural one, baked into menu pricing at generation time. Sakura Table draws menu prices from a higher range (`SAKURA_PRICE_RANGES` in `generators.py`, e.g. entrees $24–46) than the other four restaurants (`STANDARD_PRICE_RANGES`, entrees $11–22). Since `total_amount` is always computed from real line items at real prices, this produces a genuine, consistent gap in average transaction size.

**Verify by hand:**

```sql
SELECT r.name = 'Sakura Table' AS is_sakura, ROUND(AVG(t.total_amount), 2) AS avg_ticket
FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id
GROUP BY is_sakura;
```

**Actual result:** Sakura Table's average ticket = $83.33, vs. $39.41 for the other four restaurants combined — Sakura Table runs at **~2.1x** the cohort average, well clear of the "at least 1.3x" bar. This is the exact pattern Phase 2's peer/cohort comparison tool should surface.

This third pattern goes beyond the two examples `implementation-plan.md` names explicitly (both introduced with "e.g.") — it exists specifically to give the cohort-comparison tool a genuine, hand-verifiable structural difference to detect.

---

## Controls

Casa Verde and Harbor & Vine receive **no deliberate multiplier at all**. They exist so that verifying "Golden Skillet is different" or "Sakura Table is different" means something — a real deviation from an otherwise-shared baseline, not generic randomness that happens to look patterned.

---

## Read-only role check

Every table above is readable by the `ask_sous_readonly` role with no write access — this is the exact path Phase 2's aggregation tools and Phase 3's agent tools will use. Verify:

```bash
psql -U ask_sous_readonly -d ask_sous -c "SELECT COUNT(*) FROM transactions;"   # works
psql -U ask_sous_readonly -d ask_sous -c "INSERT INTO restaurants (name) VALUES ('x');"  # rejected
```

---

## Embedding column state (Phase 4+)

`reviews.embedding` and `campaigns.embedding` (both `vector(768)`, ADR-003) are **`NULL` by default** in a fresh clone or reseed — `seed.py` never populates them. They're only populated by running `python -m app.seed.embed_seed_data`, a separate follow-up script (`backend/app/seed/embed_seed_data.py`), which requires live Vertex AI credentials (see `docs/reference/gcp-setup.md`).

Until that script runs, `search_customer_reviews`/`search_similar_campaigns` (Phase 4) will correctly return zero matches for every restaurant — this is expected, honest "no data yet" behaviour (`WHERE embedding IS NOT NULL`), not a bug. Verify the current state at any time:

```bash
psql -U ask_sous -d ask_sous -c "SELECT COUNT(*) FROM reviews WHERE embedding IS NOT NULL;"
psql -U ask_sous -d ask_sous -c "SELECT COUNT(*) FROM campaigns WHERE embedding IS NOT NULL;"
```

Once populated with live credentials, both counts should read **138** and **16** respectively — matching every review and campaign seeded above — and re-running `embed_seed_data.py` again should leave both counts unchanged (idempotent, per ADR-008). **Status: run for real (2026-07-16)** — see `docs/decisions/013-live-credentials-verification.md`. Re-run it again after any reseed, since `seed.py` truncates and regenerates the `reviews`/`campaigns` tables (and their `id`s) from scratch, leaving the new rows' `embedding` columns `NULL` until `embed_seed_data.py` runs again.

### Review text content

`generate_reviews()` (Phase 1) originally used Faker's generic `paragraph()` text — grammatically plausible but never actually about anything, which meant real semantic search technically worked (returned nearest neighbors by cosine distance) but never found anything genuinely relevant to a query like "what are customers saying about the service?" This was discovered during live-credentials verification, not caught by any test, since no test asserted anything about review text *content*, only its presence. Fixed: review text is now drawn from `POSITIVE_REVIEW_TEMPLATES`/`MIXED_REVIEW_TEMPLATES`/`NEGATIVE_REVIEW_TEMPLATES` (`generators.py`), selected by the review's own `rating` so sentiment and rating correlate the way real reviews do, and covering genuine restaurant-review topics (service, food quality, wait times, price, ambiance) so qualitative vector search over them is actually meaningful. **Re-seed and re-embed to pick this up** in an existing local database — the fix only affects newly-generated rows, not ones already in Postgres from before this change.
