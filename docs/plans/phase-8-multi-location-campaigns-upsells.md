# Phase 8: Multi-Location Comparison, Campaign Performance, Upsell Measurement — Implementation Plan

**Date:** 2026-07-16
**Status:** In Progress
**Source:** User request (post-MVP, post-live-verification) — not in the original implementation-plan.md, since these three capabilities weren't part of the original master-plan.md scope. Treated with the same rigor as every numbered phase per the user's explicit choice.

---

## Goal

Three new, related capabilities requested directly by the user, each answerable both via the dashboard and via chat:

1. **Multi-location comparison** — select more than one restaurant at once; the dashboard shows a comparison view across the selection, and chat can answer comparison questions ("how does my Austin location compare to my other locations?").
2. **Campaign performance** — "how did the campaign we ran last month do?" requires transactions to actually be attributable to a campaign, which the current schema has no way to express (`campaigns` exists, but nothing links a `transaction` back to one).
3. **Upsell measurement** — "how are upsells doing at my selected locations?" requires a concept of an upsell in the data model, which doesn't exist yet (menu items have no add-on/upsell distinction).

All three are additive to the existing MVP — no existing behavior for a single selected restaurant changes in spirit, though the request/response shapes for `/chat` and `/dashboard` do change (see Breaking Changes below), matching this project's own precedent (ADR-011 already broke `/chat`'s contract once, deliberately, when the design called for it).

## Prerequisites

- Phases 0–7 complete, MVP working, live credentials verified (ADR-013).
- Local Postgres running, migrated, seeded.

## Design Decisions (confirmed with the user before this plan was written)

- **Upsell definition:** designated add-on menu items (e.g., "Extra Gravy," "Add Bacon"), not just any multi-item transaction. Requires a `menu_items.is_upsell` flag.
- **Campaign attribution:** a nullable `transactions.campaign_id` FK, populated synthetically in seed data (a probabilistic fraction of transactions in the days following a campaign's `sent_at` are attributed to it) — not a real promo-code mechanism, since none exists in this schema.
- **Process:** full phase treatment — plan doc, ADRs for the real design decisions, TDD, code review, `/simplify`, full doc updates.

## Breaking Changes

- **`POST /chat`** request body changes from `{restaurant_id, question}` to `{restaurant_ids, question}` (`restaurant_ids: list[UUID]`, min length 1). A single-restaurant question is just a list of one — no behavior change for that case, but every caller must update.
- **`GET /dashboard`** changes from `?restaurant_id=...` (singular) to `?restaurant_ids=...` (repeated query param, min length 1). Response shape changes to a per-location breakdown array even for a single selection, so the frontend has one shape to render regardless of selection count.
- **`POST /campaigns`** is unchanged — campaign generation is deliberately single-location only (a campaign is grounded in one restaurant's brand voice; generating "one campaign for multiple locations at once" isn't a coherent operation), enforced at the frontend by requiring exactly one restaurant selected before enabling the Campaigns panel's Generate action.

## Implementation Details

### 8.1 Schema changes

New Alembic migration adding two columns:
- `menu_items.is_upsell` (`Boolean`, `NOT NULL`, `server_default=false`) — a designated add-on item.
- `transactions.campaign_id` (`UUID`, nullable, `FK -> campaigns.id ON DELETE SET NULL`) — which campaign (if any) this transaction is attributed to.

**Tasks:**
- [ ] Write a failing integration test asserting both columns exist with correct types/nullability/constraints after migration
- [ ] Write the migration, update `app/db/models.py` (`MenuItem.is_upsell`, `Transaction.campaign_id` + relationship)
- [ ] Run `alembic upgrade head` locally, confirm test passes

### 8.2 Seed data: upsell items + campaign attribution

**Upsell items** — 2 small add-on items per restaurant added to `MENU_ITEM_POOLS`'s companion structure (not mixed into the existing pool, so the existing item-velocity/trend patterns in `seed-patterns.md` are untouched), each with `is_upsell=True` and its own small price range (~$2–6). `generate_transactions_and_items()` gains a generic upsell-attachment step: after selecting a transaction's base items (from the existing non-upsell pool, unchanged), a fixed `UPSELL_ATTACH_PROBABILITY` (~0.25) chance adds one random upsell item on top — independent of Bella Notte's existing Truffle Fries ramp pattern, which stays exactly as-is (Truffle Fries is a real orderable appetizer with its own deliberate trend pattern, not being reclassified as an "upsell" item).

**Campaign attribution** — after a restaurant's campaigns and transactions are both generated, a new pure function attributes each campaign a plausible fraction (~15–30%, seeded) of the transactions falling in a short window (~5 days) after that campaign's `sent_at`, setting their `campaign_id`. A transaction can only be attributed to one campaign (first-touch, by whichever campaign's window it falls into first, iterating campaigns in `sent_at` order) — avoids double-attribution ambiguity.

**Tasks:**
- [ ] Write failing unit tests: upsell items are correctly flagged and priced; `UPSELL_ATTACH_PROBABILITY`-driven attachment produces a measurable, roughly-expected attach rate over many transactions
- [ ] Implement `UPSELL_ITEM_POOLS`, `ADDON_PRICE_RANGE`, wire into `generate_menu_items()`
- [ ] Implement the upsell-attachment step in `generate_transactions_and_items()`
- [ ] Write failing unit tests: campaign attribution only touches transactions in-window, never double-attributes, is deterministic given the fixed seed
- [ ] Implement the attribution function, wire into `seed.py`'s orchestration (after both campaigns and transactions exist for a restaurant)
- [ ] Re-seed, confirm real row-level attribution via direct query; document the new pattern in `docs/reference/seed-patterns.md`

### 8.3 New aggregation tools

All follow the established pure/impure split and `readonly_connection()` boundary (`app/agent/tools/`):

- **`compare_locations(restaurant_ids: list[UUID], start_date: date, end_date: date) -> list[RevenueSummary]`** (`locations_comparison.py`) — runs `get_revenue_summary()` per restaurant concurrently (`asyncio.gather`, matching the existing concurrency precedent in `insights.py`/`campaigns.py`), returns one summary per restaurant. Reused directly by both the new tool and the dashboard endpoint's multi-location path — not reimplemented twice.
- **`list_campaigns(restaurant_id: uuid.UUID) -> list[CampaignSummary]`** (`campaign_performance.py`) — id/name/channel/sent_at, so the model (or a human via chat) can find the right campaign to ask about by name/date without needing to already know its UUID.
- **`get_campaign_performance(campaign_id: uuid.UUID) -> CampaignPerformance`** (`campaign_performance.py`) — attributed revenue/transaction count/average ticket (from `transactions.campaign_id`), plus the same restaurant's baseline average daily revenue over an equal-length window immediately before `sent_at`, so "performance" means something (attributed revenue vs. what that restaurant normally does), not just a raw number.
- **`get_upsell_metrics(restaurant_ids: list[uuid.UUID], start_date: date, end_date: date) -> list[UpsellMetrics]`** (`upsell_metrics.py`) — per restaurant: attach rate (% of transactions containing at least one `is_upsell` item) and total upsell revenue, over the given window. Takes a list (not singular) from the start, since "measure upsells in the selected locations" was the literal request — a single-location call is just a list of one.

**Tasks (red-green-refactor, per tool):**
- [ ] Write failing unit tests for each tool's pure computation function (fixture rows, hand-computable expected values, matching Phase 2's own testing depth)
- [ ] Implement each pure function
- [ ] Write failing integration tests against the real seeded DB (confirming the tool surfaces the patterns Phase 8.2's seed changes deliberately created — a measurable attach rate, a real attributed-vs-baseline campaign comparison)
- [ ] Implement each `async def` wrapper

### 8.4 Wire into the agent: multi-restaurant chat + new tools

`tool_registry.py` gains `compare_locations`, `list_campaigns`, `get_campaign_performance`, `get_upsell_metrics` as four new LLM-callable tools (six → ten). `insights_system_instruction.py`'s template changes from a single `restaurant_id` to a list, with explicit guidance: use the single-restaurant tools when exactly one is given, `compare_locations`/`get_upsell_metrics` (which already accept a list) when more than one is given, and `list_campaigns` → `get_campaign_performance` to answer campaign-performance questions regardless of selection count. `insights.py`/`answer_question()`/`answer_question_stream()` change their `restaurant_id: uuid.UUID` parameter to `restaurant_ids: list[uuid.UUID]`. `chat.py`'s `ChatRequest` changes to `restaurant_ids: list[uuid.UUID]` (min length 1); its restaurant-existence check validates every id in the list.

**Tasks:**
- [ ] Write failing unit tests for the updated system instruction (lists all given restaurant_ids, mentions all four new tools)
- [ ] Update `build_insights_system_instruction()`
- [ ] Write failing unit tests for `answer_question`/`answer_question_stream` with a multi-restaurant-id list (mocked model calling `compare_locations`)
- [ ] Update `insights.py`
- [ ] Update `tool_registry.py`'s four new tool declarations + dispatch entries
- [ ] Write failing integration tests for `/chat` with `restaurant_ids` (single-element list unchanged behavior; multi-element list exercising `compare_locations`)
- [ ] Update `chat.py`

### 8.5 Dashboard: multi-location comparison view

`GET /dashboard` changes to `?restaurant_ids=...` (repeated), response becomes `{"locations": [{"restaurant_id", "restaurant_name", "kpis", "revenue_trend", "top_items"}, ...]}` — always an array, so the frontend has one shape whether one or many restaurants are selected. Reuses `compare_locations()`/`get_upsell_metrics()` for the underlying data rather than re-querying.

Frontend `DashboardPage.tsx`: single selection renders exactly as today (KPI row + 2 charts); multiple selections render a per-location KPI comparison table (rows = locations) plus a grouped revenue-trend chart (bars grouped by day, one series per location, CSS-drawn — no charting library, per ADR-012's existing reconciliation) and an upsell-attach-rate row in the comparison table.

**Tasks:**
- [ ] Write failing integration tests for `/dashboard` with multiple `restaurant_ids`
- [ ] Update `dashboard.py`
- [ ] Write failing Vitest test for updated `getDashboard()` (accepts a list, builds repeated query params)
- [ ] Update `api.ts`
- [ ] Write failing RTL tests for `DashboardPage`'s comparison-mode rendering
- [ ] Update `DashboardPage.tsx`

### 8.6 Frontend: multi-select restaurant switcher

`RestaurantSwitcher.tsx` becomes a checkbox-based multi-select dropdown (still no headless UI library, consistent with its existing native-element simplicity reasoning) — a trigger button showing "N locations selected" (or the single name when exactly one), opening a panel with a checkbox per restaurant plus a "Select all" toggle. `restaurant-context.tsx`'s `RestaurantProvider` changes from `selectedRestaurant: Restaurant | null` to `selectedRestaurantIds: string[]`, defaulting to `[restaurants[0].id]` (single selection, matching current behavior) rather than none. `ChatPage`/`DashboardPage` receive the full id list; `CampaignsPanel` receives only the first selected id and shows a prompt ("select exactly one location to generate a campaign") when more than one is selected, disabling its Generate action.

**Tasks:**
- [ ] Write failing tests for the updated restaurant context (multi-select state, default single selection)
- [ ] Update `restaurant-context.tsx`
- [ ] Write failing RTL tests for the checkbox multi-select `RestaurantSwitcher` (select-all, individual toggles, label reflects count)
- [ ] Update `RestaurantSwitcher.tsx`
- [ ] Write failing test for `streamChat()`/`ChatPage` sending `restaurant_ids`
- [ ] Update `api.ts`'s `streamChat()`, `ChatPage.tsx`
- [ ] Update `App.tsx`/`CampaignsPanel.tsx` for the single-vs-multi selection split

## Testing

### Integration Tests
- Full round-trip: select 3 locations → `/dashboard` comparison view with correct per-location KPIs → `/chat` "compare my locations" question correctly calls `compare_locations` → grounded comparison answer.
- Campaign performance: seed a known campaign, verify attributed revenue is measurably different from baseline in the seeded pattern, verify `/chat` "how did campaign X perform?" correctly chains `list_campaigns` → `get_campaign_performance`.
- Upsell measurement: verify the seeded ~25% attach rate is measurable via `get_upsell_metrics`, verify `/chat` "how are upsells doing?" surfaces it correctly for one and multiple selected locations.

### Manual Verification
- Real browser pass: multi-select switcher, dashboard comparison view, chat comparison/campaign/upsell questions, all against the real seeded (and re-attributed) database.
- Real live-model pass (now that credentials work): actually ask each of the three new question types and confirm the model calls the right new tool(s) and answers correctly — this project's established pattern of catching real bugs live, not just in mocked tests.

## User Acceptance Tests

- [ ] UAT-8.1: Owner selects multiple locations and sees a correct comparison on the dashboard
- [ ] UAT-8.2: Owner asks chat to compare locations and gets a grounded, correct comparison answer
- [ ] UAT-8.3: Owner asks chat about a specific past campaign's performance and gets a grounded answer referencing real attributed data
- [ ] UAT-8.4: Owner asks about upsell performance for selected locations and gets a grounded, correct attach-rate/revenue answer
- [ ] UAT-8.5: Campaigns panel correctly requires exactly one location selected before allowing generation

## Documentation Updates

- [ ] ADR: campaign attribution mechanism (synthetic, why, limitations)
- [ ] ADR: multi-restaurant chat design (restaurant_ids list, system instruction approach, why `/campaigns` stays single-location)
- [ ] Update `docs/tasks.md`, `docs/uat.md`, `docs/changelog.md`, `CLAUDE.md`, `docs/reference/seed-patterns.md`

## Security Considerations

No new security surface — all new tools go through the same `readonly_connection()` boundary; the multi-restaurant list is still just a set of UUIDs validated the same way a single one was (existence-checked before use). No new write paths from the API layer (campaign attribution happens only in seed data, not via any endpoint).

## Dependencies & Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Breaking `/chat`/`/dashboard` contract changes ripple through every existing test that hardcodes the old singular shape | Medium | High | Expected and budgeted — this plan's own task list includes updating those tests as part of each sub-section, not a surprise to discover later |
| Synthetic campaign attribution is not how real POS attribution would work | Low | N/A | Explicitly a seed-data simulation, documented as such in the new ADR — real attribution would need a real promo-code/referral mechanism this project's scope doesn't include |
| Re-seeding shifts row counts again (same reason as the review-content fix) | Low | High | Already an accepted, documented, harmless consequence of the shared RNG stream (ADR-004) — update `seed-patterns.md`'s current-counts line same as before |
