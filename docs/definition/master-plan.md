# Ask Sous — Master Plan

**A grounded chat agent over restaurant transaction data, built solo as an interview-ready demo of a real production architecture, scaled down.**

**Version:** 1.0
**Author:** Surendra Devarashetty
**Date:** 2026-07-15
**Status:** Draft

---

## 1. Overview

Ask Sous is a personal rebuild of an "Ask Sous"-style agent: a chat interface over restaurant transaction data, backed by a local Postgres database and Google Vertex AI (Gemini Flash 2.5), that answers a restaurant owner's natural-language questions about their business and drafts marketing campaign copy grounded in their actual performance and brand voice. It mirrors a real "Scenario 4" system architecture — deterministic aggregation, tool-calling retrieval, generation, and output — scaled down to something buildable solo, with Postgres standing in for BigQuery and pgvector standing in for a dedicated vector store.

The point of building this isn't just a working demo — it's being able to say, in an interview, "I built a lite version of this myself" and back that up with specific, concrete answers about the tradeoffs actually encountered, not recall of a design that was never implemented.

### 1.1 Problem Statement

Restaurant owners have transaction, review, and campaign data scattered across systems, but no easy way to ask plain questions of it ("why was revenue down this week?", "what's my best-selling item on weekends?") or generate marketing copy that's actually grounded in their numbers and brand voice. Existing tools require either manual analysis or hand-written SQL. This project demonstrates a working, grounded-answer agent that solves this at demo scale — and, more importantly for its actual purpose, gives its builder hands-on experience with the tradeoffs of building such a system.

### 1.2 Goals

- Build a working demo where a restaurant owner can ask natural-language questions and get answers computed from real transaction data — never invented numbers.
- Build a campaign-copy generator that grounds its output in the restaurant's actual performance data, brand voice, and past campaign examples.
- Faithfully shrink a real, layered agent architecture (ingestion → deterministic aggregation → retrieval/routing → generation → output) rather than building a different, simpler design.
- Demonstrate a working model-routing pattern: a fast/cheap default model, with escalation to a stronger model for higher-stakes generation.
- Produce a system whose correctness can be independently verified by hand against the seed data, so its builder can defend every claim the agent makes under interview questioning.

### 1.3 Non-Goals (v1)

- Real per-second streaming ingestion (Kafka, etc.) — v1 uses a seed script plus an optional background job that inserts fake transactions on a timer to simulate "live" data.
- Actual SMS/email sending — campaigns are drafted and displayed, never sent.
- Authentication or multi-user accounts.
- Production-grade observability, rate limiting, or cost controls beyond basic logging.
- Real streaming ingestion via Kafka or Postgres logical replication.
- Multi-tenant auth, A/B testing frameworks for campaign copy, or cohort/benchmark privacy hardening (e.g. k-anonymity) — irrelevant at demo scale with fake data, but worth naming for v2 if this were ever extended toward real tenant data.

---

## 2. Users & Roles

Ask Sous has a single user persona and no authentication in v1.

### 2.1 Restaurant Owner (sole persona)

- Asks natural-language questions about their business via a chat interface and receives grounded answers.
- Requests marketing campaign copy (e.g. "draft an SMS campaign for slow Tuesday nights") and receives copy grounded in their performance data and brand voice.
- Switches between five dummy restaurants via a dropdown, to explore different data profiles and demo cohort comparisons — this is a data-context switcher, not a login or role change.

There is no admin role, no login flow, and no multi-user access model. All access control lives at the system level (see §5), not the user level.

---

## 3. Core Concepts

### 3.1 Restaurant
- **Properties:** id, name, cuisine, city, region, size category, brand voice guide (text).
- **Relationships:** has many menu items, transactions, reviews, and campaigns.

### 3.2 Menu Item
- **Properties:** id, restaurant_id (fk), name, category, price.
- **Relationships:** belongs to a restaurant; referenced by transaction items.

### 3.3 Transaction
- **Properties:** id, restaurant_id (fk), transaction_time, total_amount, payment_type, channel (dine-in / takeout / delivery).
- **Relationships:** belongs to a restaurant; has many transaction items.

### 3.4 Transaction Item
- **Properties:** transaction_id (fk), menu_item_id (fk), quantity, unit_price.
- **Relationships:** links a transaction to the menu items it contained.

### 3.5 Review
- **Properties:** id, restaurant_id (fk), rating, review_text, source, created_at, embedding (vector, for pgvector similarity search).
- **Relationships:** belongs to a restaurant.

### 3.6 Campaign
- **Properties:** id, restaurant_id (fk), name, channel, sent_at, copy_text, conversion_rate, revenue_lift, embedding (vector, on copy_text, for few-shot retrieval).
- **Relationships:** belongs to a restaurant.

Seed data is deliberately patterned (e.g. one restaurant genuinely slower on Tuesdays, one menu item genuinely trending up) so that agent answers can be verified by hand, not just judged as "plausible-sounding."

---

## 4. Feature Specification

### 4.1 Data Layer

The system stores multiple restaurants, each with menu items, transactions, transaction line items, reviews, brand voice guides, and past campaigns. A seed script generates realistic dummy data: at minimum 5 restaurants and 90 days of transaction history, varied by day-of-week and time-of-day so that questions like "why was I slower this week" have a real, discoverable answer. An optional background generator inserts a trickle of new transactions on a timer, so the demo feels live rather than static — this runs automatically on its own timer with no manual controls (per the testability decision in §8).

### 4.2 Insights Q&A

The owner asks a natural-language question and the agent returns a grounded answer computed from real data — never a number it invented. The agent has:
- Tool access to run parameterised, read-only SQL queries against Postgres for anything not already pre-aggregated.
- A small set of pre-built aggregation tools for common questions (revenue summary, item velocity, day-over-day/week-over-week comparison, peer/cohort comparison), so it doesn't have to hand-write SQL for the 80% case.
- Vector search access (pgvector) over reviews and brand voice guides, for questions that need qualitative context alongside numbers.

Every response that cites a number must be traceable back to an actual query result. Tool calls and their raw results are logged alongside the final answer, so the builder can show "here's what it actually queried" during a demo or interview, and independently verify correctness (see §8, §10).

### 4.3 Campaign Generation

For campaign requests, the agent retrieves the restaurant's brand voice guide and 1–2 past campaign examples as few-shot grounding before generating copy. Output is displayed in a dedicated campaigns panel with a "regenerate" button — copy is never actually sent (see Non-Goals).

### 4.4 Model Routing

- Default model: Gemini Flash 2.5, for all requests.
- Campaign-generation requests route to a stronger, Pro-tier Gemini model by default, since copy quality matters more than latency/cost for this path.
- Insights questions default to Flash 2.5, with a simple complexity heuristic (e.g. a query requiring 3+ tool calls, or an explicit request for deeper analysis) that can escalate to the stronger model. The heuristic doesn't need to be sophisticated — it exists to demonstrate the routing pattern, not to be a polished production rule.
- Which model handled each request is logged (not surfaced with a manual override control — see §8).

### 4.5 Frontend

- A chat interface where the owner types questions and sees answers, including which restaurant is currently selected.
- A restaurant switcher (dropdown) to flip between the dummy restaurants and demo cohort comparisons.
- A campaigns panel showing generated campaign drafts, with a "regenerate" button.
- (Nice-to-have) A small dashboard with 2–3 pre-computed charts (revenue trend, top items) for visual demo value — not core to the agent story.

---

## 5. Permissions Model

There are no user roles to differentiate, but there is a hard system-level access boundary that matters for the "grounded, not reckless" story:

| Actor | Access | Notes |
|---|---|---|
| Agent's DB connection | Read-only | Dedicated read-only Postgres role. The agent must never have write/delete access to the database, even in a demo. |
| Seed/setup scripts | Read-write | Run outside the agent's connection, using separate credentials. |
| Owner (via chat UI) | Read-only, scoped to selected restaurant's data | The UI only ever surfaces data for the currently selected restaurant; there's no cross-restaurant data leakage in the chat experience itself (cohort comparisons are an explicit, intentional aggregation feature, not a leak). |

---

## 6. Integrations

### 6.1 Google Vertex AI (Gemini)

The sole external integration. The system calls Vertex AI's Gemini models (Flash 2.5 and a Pro-tier model) via the Vertex AI SDK's native function-calling, using tool definitions for the aggregation functions, raw SQL tool, and pgvector retrieval tool. Credentials are supplied via service account, never committed to the repo (`.env`, gitignored, with a `.env.example` checked in).

There are no other external integrations in v1 — no email/SMS providers, no payment processors, no auth providers.

---

## 7. Technical Architecture

*(Full stack decisions belong to the `/cto` step — captured here as the strong existing preferences from the requirements doc, to carry forward.)*

- **Database:** Postgres (local, via Docker), with the `pgvector` extension enabled.
- **Backend:** Python, FastAPI — hosts agent logic, tool functions, and a `/chat` endpoint.
- **Agent / LLM:** Google Vertex AI SDK, calling Gemini Flash 2.5 (default) and a Pro-tier Gemini model (escalation path) directly — no LangChain/LlamaIndex layer, since a direct SDK call is simpler to build and easier to explain in an interview.
- **Frontend:** React (Vite) or Next.js — chat UI, campaigns panel, restaurant switcher.
- **Seed data:** Python + Faker, via a re-runnable, idempotent `seed.py`.
- **Local orchestration:** `docker-compose` for Postgres + FastAPI backend; frontend run separately via `npm run dev` during development.

### Data model

See §3 for entities. In Postgres terms:

```
restaurants
  id, name, cuisine, city, region, size_category, brand_voice_guide (text)

menu_items
  id, restaurant_id (fk), name, category, price

transactions
  id, restaurant_id (fk), transaction_time, total_amount, payment_type, channel

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

### Non-functional requirements

- All SQL tools are read-only — no write/delete access from the agent, ever. Use a dedicated read-only Postgres role for the agent's DB connection.
- Vertex AI credentials are never committed — `.env`, gitignored, with `.env.example` checked in.
- Every agent turn logs the user's question, the tool calls made, their raw results, and the final answer, so correctness can be audited during development and demoed credibly.
- Target response time under ~5 seconds for insights questions; up to ~15 seconds acceptable for campaign generation.

### Architecture mapping

| Layer | v1 implementation |
|---|---|
| Ingestion | Seed script (Faker-generated) + optional background trickle-inserter |
| Deterministic aggregation | SQL views / pre-built aggregation functions in Postgres — no separate stream processor or OLAP warehouse at this scale |
| Retrieval & routing | Gemini function-calling handles intent parsing; tools = structured query functions + pgvector similarity search; a Python function assembles tool results into the grounded prompt |
| Generation | Gemini Flash 2.5 default, Pro-tier for campaigns/escalated complex queries |
| Output | Chat UI + campaigns panel |

This is a faithful shrink of the real architecture — same layers, same separation of concerns (deterministic math stays in SQL, not the model) — just without the distributed infrastructure that only makes sense at production scale.

---

## 8. Testability

- **Single user persona, no auth:** no test-account matrix needed.
- **Background trickle generator:** runs automatically on its own timer alongside the backend. No manual on/off toggle or "insert now" trigger was requested — it's a nice-to-have polish feature and doesn't need on-demand testing infrastructure.
- **Model routing:** which model (Flash vs Pro-tier) handled each request is logged per turn, satisfying the audit trail already required by the NFRs. No manual override to force a specific route was requested — the routing heuristic is expected to be exercised naturally through normal testing (asking a campaign question exercises the Pro-tier path; asking a simple insights question exercises Flash).
- **External integration (Vertex AI):** no sandbox/test-mode distinction needed since there's no cost-sensitive side effect (no real messages sent, no charges) — normal API usage during development doubles as testing.

---

## 9. Success Metrics

The primary success bar is **verifiable correctness**, not breadth or performance:

- For a fixed set of test questions per restaurant, the builder can independently verify the agent's numeric answers by hand against the seed data — zero fabricated numbers.
- Every claim the agent makes is traceable back to a logged tool call and its raw result.
- Secondary: response times land within the NFR targets (~5s insights, ~15s campaigns) consistently enough not to undermine a live demo.
- Ultimate measure of success (stated goal): the builder can discuss the system's real tradeoffs — model routing, grounding, read-only data boundaries, shrinking a distributed architecture to a single-node demo — concretely and specifically in an interview setting.

---

## 10. Future Considerations (Post-v1)

- Real streaming ingestion (Kafka, or Postgres logical replication feeding a stream).
- Actual SMS/email sending for real campaign delivery.
- Multi-tenant authentication.
- A/B testing framework for campaign copy variants.
- Cohort/benchmark privacy hardening (e.g. k-anonymity thresholds), relevant only if this were ever extended to touch real tenant data.
- Open decisions to confirm before/during build: exact Gemini Pro-tier model to use for escalation (check current Vertex AI model availability, since it will have moved since original interview prep); how many dummy restaurants and how much transaction history is "enough" for cohort comparisons to feel real (starting point: 5 restaurants / 90 days, expand if needed).
