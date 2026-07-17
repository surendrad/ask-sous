# Ask Sous — Requirements & Build Plan

A personal-project rebuild of the "Ask Sous" agent: a chat interface over restaurant transaction
data, backed by a local Postgres database and Google Vertex AI (Gemini Flash 2.5), that answers owner
questions and drafts marketing campaign copy. This mirrors the Scenario 4 architecture from your
interview prep, scaled down to something buildable solo, with Postgres standing in for BigQuery and
pgvector standing in for a separate vector store.

---

## 1. Project Goal

Build a working demo where a restaurant owner can:
1. Ask natural-language questions about their business ("why was revenue down this week?", "what's my
   best-selling item on weekends?") and get grounded, accurate answers computed from real transaction data.
2. Ask for a marketing campaign ("draft an SMS campaign for slow Tuesday nights") and get copy that's
   grounded in their actual performance data and their brand voice.

The point of building this isn't just a working app — it's being able to say in an interview "I built a
lite version of this myself" and have specific, concrete answers about the tradeoffs, not just recall
of a design you didn't implement.

---

## 2. Scope for v1

**In scope:**
- Local Postgres with realistic dummy restaurant transaction data (multiple restaurants, so cohort
  comparisons are possible)
- A Gemini Flash 2.5 agent with tool-calling access to the database (structured queries) and to
  reviews/brand-voice text (vector search via pgvector)
- Insights Q&A: answers grounded in actual computed numbers, not model guesses
- Campaign copy generation: grounded in performance data + brand voice + past campaign examples
- A simple model-routing rule: Flash 2.5 by default, escalate to a stronger Gemini model for campaign
  generation or when a query is flagged as complex
- A basic web chat UI, plus a lightweight panel showing drafted campaigns

**Explicitly deferred to v2 (call this out in the doc, don't build it now):**
- Real per-second streaming ingestion (Kafka, etc.) — v1 uses a seed script + an optional background
  job that inserts new fake transactions every few seconds to simulate "live" data
- Actual SMS/email sending — campaigns are drafted and displayed, not sent
- Authentication / multi-user accounts
- Production-grade observability, rate limiting, cost controls beyond basic logging

---

## 3. Functional Requirements

### 3.1 Data layer
- FR1: System stores multiple restaurants, each with menu items, transactions, transaction line items,
  reviews, brand voice guides, and past campaigns.
- FR2: A seed script generates realistic dummy data — at minimum 5 restaurants, 90 days of transaction
  history, varied by day-of-week and time-of-day patterns (so "why was I slower this week" has a real
  answer to find).
- FR3: (Optional, nice-to-have) A background generator inserts a trickle of new transactions on a timer,
  so the demo feels live rather than static.

### 3.2 Agent / query layer
- FR4: The agent accepts a natural-language question from the owner and returns a grounded answer —
  never a number it invented.
- FR5: The agent has tool access to run parameterized, read-only SQL queries against Postgres for
  anything not already pre-aggregated.
- FR6: The agent has a small set of pre-built aggregation tools for common questions (revenue summary,
  item velocity, day-over-day/week-over-week comparison, peer/cohort comparison) so it doesn't have to
  hand-write SQL for the 80% case.
- FR7: The agent has vector search access (pgvector) over reviews and brand voice guides, for
  questions/campaigns that need qualitative context, not just numbers.
- FR8: For campaign requests, the agent retrieves the restaurant's brand voice guide and 1–2 past
  campaign examples as few-shot grounding before generating copy.
- FR9: Every agent response that cites a number must be traceable back to an actual query result —
  log the tool calls and their results alongside the final answer, so you can show/debug "here's what it
  actually queried" if asked.

### 3.3 Model routing
- FR10: Default model is Gemini Flash 2.5 for all requests.
- FR11: Campaign-generation requests route to a stronger Gemini model (Pro-tier) by default, since copy
  quality matters more there than latency/cost.
- FR12: Insights questions route to Flash 2.5 by default; add a simple complexity heuristic (e.g., query
  requires 3+ tool calls, or the user explicitly asks for deeper analysis) that can escalate to the
  stronger model. This doesn't need to be sophisticated — a basic rule is enough to demonstrate the
  pattern.

### 3.4 Frontend
- FR13: A chat interface where the owner types questions and sees answers, including which restaurant
  is currently selected (since the dummy data has multiple).
- FR14: A restaurant switcher (dropdown), since you'll want to demo cohort comparisons across a couple
  of different fake restaurants.
- FR15: A campaigns panel showing generated campaign drafts, with a "regenerate" button.
- FR16: (Nice-to-have) A small dashboard showing 2–3 pre-computed charts (revenue trend, top items) so
  there's something visual beyond the chat — useful for demoing, not core to the agent story.

---

## 4. Data Model (Postgres)

```
restaurants
  id, name, cuisine, city, region, size_category, brand_voice_guide (text)

menu_items
  id, restaurant_id (fk), name, category, price

transactions
  id, restaurant_id (fk), transaction_time, total_amount, payment_type, channel
  (dine-in / takeout / delivery)

transaction_items
  transaction_id (fk), menu_item_id (fk), quantity, unit_price

reviews
  id, restaurant_id (fk), rating, review_text, source, created_at
  -- embedding column (vector) for pgvector similarity search

campaigns
  id, restaurant_id (fk), name, channel, sent_at, copy_text,
  conversion_rate, revenue_lift
  -- embedding column (vector) on copy_text, for few-shot retrieval
```

Notes:
- `reviews.embedding` and `campaigns.embedding` are `vector` columns (pgvector extension) — this is
  what stands in for the separate vector DB in the full architecture. Same tradeoff you already
  documented in Scenario 1/2: start with pgvector in the same Postgres instance rather than standing up
  a dedicated vector store, since it's a demo-scale dataset.
- Seed data should have deliberate patterns baked in (e.g., one restaurant genuinely slower on Tuesdays,
  one item genuinely trending up) so that when the agent answers a question, you can verify by hand that
  the answer is actually correct — not just plausible-sounding.

---

## 5. Agent Architecture (mapped to your Scenario 4 layers)

| Scenario 4 layer | v1 implementation |
|---|---|
| 1. Ingestion | Seed script (Faker-generated data) + optional background trickle-inserter for a "live" feel |
| 2. Deterministic aggregation | SQL views / a handful of pre-built aggregation functions in Postgres — no separate stream processor or OLAP warehouse needed at this scale |
| 3. Retrieval & routing | Gemini function-calling (tool use) handles intent parsing natively; tools = structured query functions + pgvector similarity search; a small Python function assembles tool results into the grounded prompt |
| 4. Generation | Gemini Flash 2.5 default, Gemini Pro-tier for campaigns / escalated complex queries |
| 5. Output | Chat UI + campaigns panel |

This is a faithful shrink of the real architecture, not a different design — same layers, same
separation of concerns (deterministic math stays in SQL, not in the model), just without the
distributed infrastructure that only makes sense at restaurant tech's actual scale.

---

## 6. Tech Stack

- **Database:** Postgres (local, via Docker) with the `pgvector` extension enabled
- **Backend:** Python, FastAPI — hosts the agent logic, tool functions, and a `/chat` endpoint
- **Agent / LLM:** Google Vertex AI SDK, Gemini Flash 2.5 (default) + a Pro-tier Gemini model
  (escalation path)
- **Frontend:** React (Vite) or Next.js — simple chat UI + campaigns panel + restaurant switcher
- **Seed data:** Python + Faker, a `seed.py` script that's re-runnable and idempotent
- **Local orchestration:** `docker-compose` with two services — Postgres and the FastAPI backend;
  frontend run separately via `npm run dev` during development

---

## 7. Non-Functional Requirements

- NFR1: All SQL tools are read-only — no write/delete access from the agent, ever, even in a demo.
  Use a dedicated read-only Postgres role for the agent's DB connection.
- NFR2: Vertex AI API keys/service account credentials are never committed to the repo — use a
  `.env` file, gitignored, with a `.env.example` checked in instead.
- NFR3: Every agent turn logs: the user's question, the tool calls made, their raw results, and the
  final answer — so you can audit correctness during development and demo the "grounded, not
  hallucinated" story credibly.
- NFR4: Target response time under ~5 seconds for insights questions, acceptable up to ~15 seconds for
  campaign generation (matches the real system's latency profile — cheap/fast for facts, slower is fine
  for higher-stakes generation).

---

## 8. Build Milestones

1. **Data layer** — Postgres schema, seed script, verify data looks realistic by querying it directly.
2. **Aggregation tools** — write and unit-test the pre-built SQL aggregation functions before wiring up
   the agent at all. You want to know these are correct independent of the LLM.
3. **Agent core** — wire up Gemini Flash 2.5 with function calling against the aggregation tools and a
   raw read-only SQL tool. Get insights Q&A working end-to-end via a CLI or simple API call, before
   building any UI.
4. **Vector retrieval** — add pgvector, embed reviews and past campaigns, add the retrieval tool.
5. **Campaign generation** — add the campaign-copy tool/prompt path, wire up model routing to the
   stronger model for this path.
6. **Frontend** — chat UI, restaurant switcher, campaigns panel.
7. **Polish for demo** — the optional live-trickle data generator, the nice-to-have dashboard charts.

Build in this order — get the agent answering real questions correctly against raw SQL and pre-built
tools before touching the frontend at all. It's much easier to debug grounding issues from a terminal
than through a chat UI.

---

## 9. Stretch Goals / v2 (don't build now, just note)

- Real streaming ingestion (Kafka or Postgres logical replication → a stream)
- SMS/email sending integration for real campaign delivery
- Multi-tenant auth
- A/B testing framework for campaign copy variants
- Cohort/benchmark privacy hardening (k-anonymity thresholds) if this ever touched real tenant data

---

## 10. Open Decisions to Confirm Before You Start Building

- Exact Gemini Pro-tier model to use for escalation (check current Vertex AI model availability —
  this will have moved since the interview prep was written)
- Whether to use LangChain/LlamaIndex as an agent framework, or call the Vertex AI SDK's native
  function-calling directly (direct SDK is simpler for a project this size and easier to explain in an
  interview — recommend starting there)
- How many dummy restaurants and how much transaction history is "enough" to make cohort comparisons
  feel real (suggest starting with 5 restaurants / 90 days, expand if needed)
