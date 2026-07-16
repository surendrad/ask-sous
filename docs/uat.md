# Ask Sous — User Acceptance Tests

Status indicators: ⬜ Not Started · ✅ Passed · ❌ Failed

---

## Phase 0: Project Foundation

### UAT-0.1: Local environment starts successfully

**Status:** ⬜ Not Started

**Steps:**

1. Run `docker-compose up` from the project root and wait for the log output to settle.
2. Open a web browser to `http://localhost:8000/health`.

**Expected:**

- The page shows JSON text containing `"status": "ok"` inside a `data` object, with `"error": null`.

### UAT-0.2: Frontend shell loads and confirms it can reach the backend

**Status:** ⬜ Not Started

**Steps:**

1. With the backend still running from UAT-0.1, open a terminal, run `cd frontend && npm run dev`, and open the printed local URL (typically `http://localhost:5173`) in a browser.

**Expected:**

- A card appears reading "Ask Sous" with a small store icon, and a green-tinted pill showing the backend's status as "ok" a moment after the page loads.

### UAT-0.3: Design system renders correctly

**Status:** ⬜ Not Started

**Steps:**

1. On the same page from UAT-0.2, check the heading font, background/card tones, and accent colour.

**Expected:**

- The heading font looks like a warm, rounded serif (not a plain sans-serif).
- The app background and card have a warm off-black (dark mode) or warm cream (light mode) tone — not pure white/black or blue-grey.
- The accent colour on any highlighted element is a warm orange/terracotta, not a generic blue or red.
- Overall, the visual tone reads as warm and "hospitality" rather than generic tech-blue, matching the "Warm Ember" direction agreed during design.

---

## Phase 1: Data Layer

### UAT-1.1: Database seeds successfully with realistic data

**Status:** ⬜ Not Started

**Steps:**

1. With the backend environment set up and migrations applied, run `cd backend && python -m app.seed.seed` from a terminal.

**Expected:**

- The terminal prints a summary showing 5 restaurants and non-zero counts for menu items, transactions, transaction items, reviews, and campaigns.

### UAT-1.2: One restaurant is genuinely slower on Tuesdays

**Status:** ⬜ Not Started

**Steps:**

1. Open a Postgres client (`psql`, TablePlus, pgAdmin, etc.) connected to the local database and run the exact query documented under "Pattern 1 — Golden Skillet: Tuesday slowdown" in `docs/reference/seed-patterns.md`.

**Expected:**

- Golden Skillet's average Tuesday revenue is meaningfully lower (at least ~20%, typically much more) than its average revenue on other days of the week.

### UAT-1.3: One menu item is genuinely trending upward

**Status:** ⬜ Not Started

**Steps:**

1. Run the query documented under "Pattern 2 — Bella Notte: Truffle Fries trending up" in `docs/reference/seed-patterns.md`.

**Expected:**

- The total quantity of Truffle Fries sold in the most recent 30 days of the seeded window is at least double the quantity sold in the first 30 days.

### UAT-1.4: Re-running the seed script is safe and repeatable

**Status:** ⬜ Not Started

**Steps:**

1. Immediately after UAT-1.1, run `python -m app.seed.seed` a second time.

**Expected:**

- The printed summary reports the exact same row counts as the first run, and re-running the query from UAT-1.2 gives the identical numeric result both times — not just "still slower," the same number.

---

## Phase 2: Aggregation Tools

### UAT-2.1: The revenue summary tool correctly detects Golden Skillet's Tuesday slowdown

**Status:** ⬜ Not Started

**Steps:**

1. With the backend environment set up, migrations applied, and the database seeded, run a short Python script (or REPL session) that calls `get_revenue_summary()` for Golden Skillet across the full 90-day seed window and prints the average revenue per day of week.

**Expected:**

- Tuesday's average is visibly, substantially lower than every other day of the week — consistent with the ~57.7%-below-average figure documented in `docs/reference/seed-patterns.md`.

### UAT-2.2: The item velocity tool correctly detects Bella Notte's Truffle Fries trend

**Status:** ⬜ Not Started

**Steps:**

1. Run a script calling `get_item_velocity()` for Bella Notte's Truffle Fries, once over the first 30 days of the seed window and once over the last 30 days, and print both `total_quantity` values.

**Expected:**

- The last-30-days quantity is at least double (documented as ~3.0x) the first-30-days quantity.

### UAT-2.3: The cohort comparison tool correctly detects Sakura Table's premium ticket size

**Status:** ⬜ Not Started

**Steps:**

1. Run a script calling `get_cohort_comparison()` for Sakura Table with `metric="average_ticket"` over the full seed window, and print `restaurant_value`, `peer_value`, and `ratio_to_peers`.

**Expected:**

- Sakura Table's average ticket is at least 1.3x (documented as ~2.1x) the pooled average of the other four restaurants.

### UAT-2.4: The period comparison tool explains a specific slow day

**Status:** ⬜ Not Started

**Steps:**

1. Run a script calling `compare_periods()` for a Tuesday at Golden Skillet (any Tuesday well inside the 90-day window) and print `current_revenue`, `prior_revenue`, and `revenue_change_pct`.

**Expected:**

- The tool reports that Tuesday's revenue is meaningfully (at least 25%, typically much more) below the immediately preceding Monday's — a concrete, hand-checkable answer to "why was revenue down that day."

## Phase 3: Agent Core (Insights Q&A)

### UAT-3.1: The agent answers a data question using a real tool call, with mocked model output

**Status:** ⬜ Not Started

**Steps:**

1. With the backend running and a test script/fixture standing in for `GeminiClient` (no live credentials needed), send a request equivalent to "what was Golden Skillet's revenue last month?" to `POST /chat`.

**Expected:**

- The response includes a non-empty `tool_calls` array naming `get_revenue_summary` with real arguments and a real, numeric result matching what's independently known from `docs/reference/seed-patterns.md`.

### UAT-3.2: A malformed or unanswerable question doesn't crash the agent

**Status:** ⬜ Not Started

**Steps:**

1. Send `POST /chat` with a nonsensical or out-of-scope question (e.g. "what's the weather today?").

**Expected:**

- A clean `200` response with a sensible "I can't answer that" style reply (or, if it triggers the round-cap, a clean `502 agent_incomplete` error) — never a raw stack trace or `500`.

### UAT-3.3: An invalid restaurant ID is rejected cleanly

**Status:** ⬜ Not Started

**Steps:**

1. Send `POST /chat` with a syntactically valid but non-existent `restaurant_id` (any random UUID).

**Expected:**

- A `404` response with `code="restaurant_not_found"`, not a crash or a misleading "agent unavailable" error.

### UAT-3.4: Every claim in a response is traceable in the logs

**Status:** ⬜ Not Started

**Steps:**

1. After UAT-3.1's request, tail the backend's structlog output for that request's `turn_id`.

**Expected:**

- Every number that appears in the final `answer` text also appears in one of the logged `tool_call_result` events for that same `turn_id`.

### UAT-3.5: The agent answers a real question end-to-end using a genuine Gemini Flash 2.5 call

**Status:** ⬜ Not Started (requires live Vertex AI credentials — complete `docs/reference/gcp-setup.md` first)

**Steps:**

1. With `.env` populated with real GCP values, start the backend and send `POST /chat` with a real natural-language question for one of the five seeded restaurants (e.g. "why was revenue down last Tuesday?" for Golden Skillet).

**Expected:**

- A real answer is returned within roughly 5 seconds, it correctly names Tuesday as the slow day, the `tool_calls` array shows real Gemini-issued function calls (not a fixture), and the cited numbers can be independently verified against `docs/reference/seed-patterns.md`.

### UAT-3.6: The raw SQL tool is actually usable by a real model for a question the pre-built tools can't answer

**Status:** ⬜ Not Started (requires live Vertex AI credentials)

**Steps:**

1. Ask a question that has no matching pre-built aggregation tool (e.g. "what payment type is most common at Sakura Table?").

**Expected:**

- The model chooses `run_readonly_query`, the logged query is genuinely a `SELECT`, and the answer is correct.

## Phase 4: Vector Retrieval

### UAT-4.1: The agent answers a qualitative question using the review-search tool

**Status:** ⬜ Not Started

**Steps:**

1. With the backend running, `EmbeddingClient` mocked, and a small set of seeded reviews hand-embedded with known vectors (test fixture setup), send a request equivalent to "what are customers saying about the service?"

**Expected:**

- The response's `tool_calls` array names `search_customer_reviews` with a real `query` argument and real review text/ratings in its result, and the final answer's claims about review content are traceable to that result.

### UAT-4.2: Review search is scoped to the correct restaurant

**Status:** ⬜ Not Started

**Steps:**

1. With two restaurants' reviews hand-embedded such that a review belonging to a *different* restaurant would otherwise be the nearest match, send a request scoped to the first restaurant.

**Expected:**

- The second restaurant's review never appears in either `tool_calls` or the final answer.

### UAT-4.3: A qualitative question asked before embeddings exist returns an honest "no data" answer

**Status:** ⬜ Not Started

**Steps:**

1. Before running `embed_seed_data.py` (the default state of this environment's database right now), ask a qualitative review question.

**Expected:**

- The tool call completes with zero matches and the agent's answer honestly states it has no review data to draw on, rather than inventing plausible-sounding review content — not a crash.

### UAT-4.4: The embedding population script runs successfully against real data

**Status:** ⬜ Not Started (requires live Vertex AI credentials — complete `docs/reference/gcp-setup.md` first)

**Steps:**

1. With `.env` populated with real GCP values, run `python -m app.seed.embed_seed_data`.
2. Run `SELECT COUNT(*) FROM reviews WHERE embedding IS NOT NULL;` via `psql` directly.
3. Re-run the script a second time.

**Expected:**

- The script completes without error and reports `reviews embedded: 138` and `campaigns embedded: 16`; the `psql` query confirms all 138 review rows (and all 16 campaigns) are populated. The second run completes again with identical row counts (idempotency holds against the real model, not just the mocked test).

### UAT-4.5: A live qualitative search returns semantically relevant reviews

**Status:** ⬜ Not Started (requires live Vertex AI credentials)

**Steps:**

1. After UAT-4.4, ask a real natural-language qualitative question for one of the five seeded restaurants (e.g. "what do customers say about wait times at Golden Skillet?").

**Expected:**

- The reviews returned by `search_customer_reviews` in the response's `tool_calls` are genuinely topically relevant (mention service speed, waiting, etc.) rather than semantically unrelated matches, and the final answer's characterisation of customer sentiment is faithful to what those specific reviews say.

## Phase 5: Campaign Generation

### UAT-5.1: Owner requests a campaign and receives copy grounded in their brand voice

**Status:** ⬜ Not Started

**Steps:**

1. Send a `POST /campaigns` request for a seeded restaurant with a brief (e.g. "Announce our new weekend brunch special").

**Expected:**

- The response's `copy_text` is present, non-empty, and its tone is plausibly consistent with that restaurant's `brand_voice_guide` (spot-check by reading both side by side); `model` is `gemini-2.5-pro`.

### UAT-5.2: Campaign copy reflects retrieved past-campaign style when similar past campaigns exist

**Status:** ⬜ Not Started

**Steps:**

1. With at least one past campaign embedded for a restaurant (via `embed_seed_data.py` once live credentials exist, or a hand-embedded fixture row), send a `POST /campaigns` request with a brief similar in theme to that past campaign.

**Expected:**

- `examples_used` in the response is non-empty and names a real campaign from that restaurant; the generated copy's style is plausibly influenced by the retrieved example rather than generic.

### UAT-5.3: Campaign generation for a restaurant with no past campaign examples still succeeds

**Status:** ⬜ Not Started

**Steps:**

1. Send a `POST /campaigns` request for a restaurant with no embedded past campaigns (the default state before `embed_seed_data.py` has been run against live credentials).

**Expected:**

- The request still succeeds (200, not an error); `examples_used` is an empty list; the generated copy is still grounded in the brand voice guide alone.

### UAT-5.4: A simple insights question still routes to Flash

**Status:** ⬜ Not Started

**Steps:**

1. Ask a straightforward insights question (e.g. "how much revenue did I make last week?") via `POST /chat`.
2. Inspect the server logs for the `agent_turn_model_selected` event(s) for that turn.

**Expected:**

- Every `agent_turn_model_selected` event for the turn shows `model=gemini-2.5-flash` and `routing_reason=default`; the response's `model` field is `gemini-2.5-flash`.

### UAT-5.5: A complex, multi-tool-call insights question escalates to Pro mid-turn

**Status:** ⬜ Not Started (requires live Vertex AI credentials)

**Steps:**

1. Ask a question likely to require several rounds of investigation (e.g. a broad, open-ended "what's going on with my business lately?" style question) via `POST /chat`.
2. Inspect the server logs for the sequence of `agent_turn_model_selected` events for that turn.

**Expected:**

- The turn starts on `gemini-2.5-flash`/`routing_reason=default`, and — once it has genuinely needed 3+ tool-call rounds without a final answer — a later `agent_turn_model_selected` event in the same `turn_id` shows `model=gemini-2.5-pro`/`routing_reason=tool_call_threshold`; the final response's `model` field is `gemini-2.5-pro`.

### UAT-5.6: An explicit "give me a deep dive" question routes straight to Pro

**Status:** ⬜ Not Started (requires live Vertex AI credentials)

**Steps:**

1. Ask a question explicitly requesting deeper analysis (e.g. "Can you give me a deep dive on my weekday vs weekend performance?") via `POST /chat`.
2. Inspect the server logs for the `agent_turn_model_selected` event(s) for that turn.

**Expected:**

- The very first `agent_turn_model_selected` event for the turn (round 0, before any tool call) already shows `model=gemini-2.5-pro`/`routing_reason=keyword`, not just a later one.
