# ADR-014: Campaign Attribution Mechanism

**Date:** 2026-07-16
**Status:** Accepted

## Context

The user asked (Phase 8, item 2) for the ability to measure "performance of a campaign we might have run in the past," and specified the shape of the fix themselves when asked to clarify: "we need seed data with some campaigns for each location and some transactions with the campaign used." There is no real ad-platform integration in this project (no Meta/Google Ads webhook, no UTM-parameter capture at checkout) — `campaigns` already existed as a table (Phase 5, campaign copy generation) but had no link to `transactions` at all. Something had to decide, for each transaction, whether it "belongs" to a campaign, and that decision has to happen somewhere since no real attribution data exists to seed from.

## Decision

**A nullable `transactions.campaign_id` foreign key (`ON DELETE SET NULL`), populated only in the seed script via synthetic probabilistic attribution — never computed at query time or via any write-capable API endpoint.**

`app/seed/generators.py`'s `attribute_transactions_to_campaigns()` runs once, after both `transactions` and `campaigns` have been generated for a restaurant:

1. Only campaigns with a `sent_at` timestamp are eligible (a campaign still in draft, never sent, has nothing to attribute).
2. For each sent campaign, in chronological order, a fixed `CAMPAIGN_ATTRIBUTION_WINDOW_DAYS = 5` window immediately after `sent_at` defines the candidate pool — a transaction more than 5 days after a campaign went out isn't a plausible result of it.
3. A random attach rate is drawn per campaign from `CAMPAIGN_ATTRIBUTION_RATE_RANGE = (0.15, 0.30)` (mirroring the realism reasoning already established for upsell attach rates — see the upsell tool's own docstring), and that fraction of the window's candidate transactions is sampled and stamped with `campaign_id`.
4. Attribution is first-touch and non-overlapping: once a transaction is attributed to a campaign, it's removed from the candidate pool for every later campaign, so multiple campaigns can never double-claim the same transaction — a design chosen for query-side simplicity (`get_campaign_performance()` never has to reason about split/fractional attribution), not because real multi-touch attribution doesn't exist.
5. The whole process is deterministic — driven by the seed script's `Random` instance (`FIXED_SEED = 42`), not real time-of-day randomness — so seeded data is reproducible across `seed.py` runs, matching every other generator in this file.

`app/agent/tools/campaign_performance.py`'s `get_campaign_performance()` reads this column directly: attributed revenue/transaction count is a `WHERE campaign_id = :campaign_id` aggregate, and a baseline is computed from the same restaurant's revenue in the `BASELINE_WINDOW_DAYS = 5` window immediately *before* `sent_at` — an equal-length "what this restaurant normally does" comparison point, not a global average.

## Consequences

- `campaign_id` is genuinely synthetic — it does not reflect any real causal claim that a purchase happened *because of* the campaign. This is fine for a demo/interview-conversation project whose whole point is showing grounded retrieval over realistic-looking data, but would be a serious problem if this schema/tool were ever pointed at a real restaurant's data expecting real marketing-attribution accuracy. `list_campaigns`/`get_campaign_performance`'s tool descriptions and this ADR are the record of that limitation; nothing in the product surface currently disclaims it to an end user, which would need to change before any real deployment.
- Because attribution only ever happens in the seed script, `transactions.campaign_id` is immutable from every live code path — no endpoint writes it, so the read-only DB boundary (`readonly_connection()`) that all agent tool code goes through is never at risk of trying to mutate it. This was a deliberate scope-limiting choice from the original clarifying-questions exchange ("Add `transactions.campaign_id`, synthetic attribution in seed data") over the alternative of a live attribution service.
- `ON DELETE SET NULL` (not `CASCADE` or `RESTRICT`) means deleting a campaign row silently un-attributes its transactions rather than deleting real transaction history or blocking the delete — consistent with treating `campaigns` as strictly secondary/derived data relative to `transactions`, which is the actual transaction-of-record.
- The bulk-insert order in `seed.py` had to change (`Campaign` before `Transaction`) once this FK existed — a real bug caught during implementation via the integration test suite, not anticipated in the original plan. Documented here so a future schema change involving insert ordering doesn't get bitten by the same thing again.

## Alternatives Considered

- **Deterministic rule-based attribution (e.g. "the campaign's featured item purchased within N days").** Rejected: `campaigns.featured_item_ids` already excludes upsell items but isn't guaranteed to correlate with any particular transaction's contents in the synthetic seed data, and a rule this specific would produce an attach rate driven entirely by how often that item happens to appear — not a realistic, controllable rate. The probabilistic approach lets the attach rate be tuned directly (`CAMPAIGN_ATTRIBUTION_RATE_RANGE`) to whatever looks realistic for a demo, independent of unrelated seed-data randomness.
- **A live attribution/write endpoint** (e.g. `POST /campaigns/{id}/attribute` letting a caller mark transactions after the fact). Rejected as unnecessary scope for a demo project with no real ad-platform integration to receive attribution signals from in the first place — see the "Add transactions.campaign_id, synthetic attribution in seed data" option the user explicitly chose over this kind of live mechanism when asked.
- **Multi-touch/fractional attribution** (a transaction can be partially attributed to more than one campaign). Rejected for the added query complexity it would push onto every consumer of `campaign_id` for a demo dataset where a handful of restaurants each run a handful of campaigns — first-touch is simpler and sufficient to prove the "did this campaign move the needle" chat/dashboard use case.
