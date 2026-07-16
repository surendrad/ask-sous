# ADR-009: Vector Retrieval Tool Design

**Date:** 2026-07-16
**Status:** Accepted

## Context

Phase 4 needs a similarity search mechanism over `reviews.embedding` and
`campaigns.embedding` (both `vector(768)`, per ADR-003) — usable now for
qualitative Q&A ("what are customers saying about X?") and, in Phase 5, for
retrieving few-shot campaign examples before generating new copy. This ADR
covers the SQL-level design decisions (distance metric, how a query vector
gets into a bound SQL parameter, indexing) and the split between the two
functions this phase builds.

## Decision

**Cosine distance (`<=>`) over Euclidean (`<->`) or inner product (`<#>`).**
Text embeddings from models like `text-embedding-004` are conventionally
compared by cosine similarity — the models are trained/evaluated with that
metric in mind, and magnitude differences between embeddings aren't
meaningful for this app's purposes (finding semantically similar review/
campaign text), only direction is. pgvector's `<=>` operator returns cosine
*distance* (`1 - cosine_similarity`), so smaller is more similar — `ORDER
BY embedding <=> :query_vector` directly gives nearest-first ordering with
no extra transformation needed.

**Vector literal bound as an ordinary text parameter, `CAST` to `vector` in
SQL** — not asyncpg-level codec registration for the `vector` type.
`_format_vector_literal()` renders a `list[float]` as pgvector's bracketed
literal syntax (`"[0.1,0.2,0.3]"`), and the query text does
`CAST(:vector_literal AS vector)`. The alternative — registering a custom
asyncpg codec so `list[float]` binds directly as a native `vector` value —
would need to run once per connection at the `readonly_connection()`
call site, coupling `db.py`'s deliberately simple per-call engine (ADR-005)
to pgvector-specific setup for every query, not just the two that need it.
The literal+`CAST` approach keeps the vector-specific logic entirely inside
`vector_search.py`, where it belongs, and the bound parameter is still a
plain string — no raw string interpolation of the vector values into SQL
text, so this doesn't reopen any injection-style concern (the values are
floats this app generated from its own embedding call, not caller-supplied
text, but keeping them parameterised is still the right default).

**No ANN index (e.g. `ivfflat`/`hnsw`) added at this data scale.** With 138
reviews and 16 campaigns total (docs/reference/seed-patterns.md), a full
sequential scan with the `<=>` operator computed per row is trivially fast
— an approximate-nearest-neighbour index exists to avoid an O(n) scan at
scales where n is large (tens of thousands+ of vectors), which doesn't
describe this demo project's data volume. Adding one now would be
premature optimisation with a real cost (index build/maintenance
complexity, and ANN indexes trade exactness for speed, which isn't a
trade-off this project needs to make).

**`search_customer_reviews` is registered as the sixth LLM-callable tool
this phase; `search_similar_campaigns` is built but deliberately left
unregistered.** `search_reviews()`'s use case — the model deciding, from a
qualitative question, when to look up review content — is exactly the kind
of judgment call function-calling is for. `search_similar_campaigns()`'s
use case (Phase 5's campaign generation few-shot retrieval) is different in
kind: Phase 5's campaign flow is expected to call it directly and
deterministically as a fixed step before generating copy, not something the
model itself decides to invoke mid-conversation. Registering it as an
LLM-callable tool now would be speculative — it isn't reachable from
anywhere until Phase 5 wires it up, and the pure/impure split already
makes it independently testable and ready to import directly. Confirmed via
`grep` that it's unreferenced by `tool_registry.py`/`INSIGHTS_TOOLS` this
phase, exactly as intended.

## Consequences

- Every review/campaign search this phase performs is provably scoped to
  the requesting restaurant — proven by an integration test asserting a
  review from a *different* restaurant, with an identical embedding, is
  never returned, not just that the `WHERE restaurant_id = :restaurant_id`
  clause is present in the SQL text.
- Rows with `embedding IS NULL` (every review/campaign in this environment
  right now, since `embed_seed_data.py` requires live credentials that
  don't exist here) are silently excluded by the `WHERE ... AND embedding
  IS NOT NULL` clause — `search_reviews()` against an unembedded restaurant
  returns an empty `matches` list, not an error, which is the honest,
  correct behaviour for "no data yet" rather than a crash.
- The real pgvector `<=>`/`ORDER BY`/`LIMIT`/restaurant-scoping SQL is
  proven correct against the actual Postgres+pgvector instance via
  hand-crafted vectors inserted directly into real seeded rows — this
  doesn't require semantically real embeddings or live credentials to
  verify the *query logic* is right, only the actual model-quality
  question (are the *results* semantically relevant) is deferred to
  UAT-4.5.
- If this project's data volume ever grew by orders of magnitude, adding
  an `ivfflat`/`hnsw` index would be a follow-up migration, not a redesign
  of the query shape itself — `ORDER BY <=> ... LIMIT` is exactly the query
  form an ANN index would accelerate.

## Alternatives Considered

- **Euclidean distance (`<->`).** Rejected: not the conventional metric
  for comparing text embeddings from this class of model; would require
  re-normalizing vectors to make magnitude differences meaningless anyway,
  which cosine distance handles natively.
- **asyncpg-level `vector` codec registration**, so Python `list[float]`
  binds natively without a `CAST`. Rejected: couples the shared, otherwise
  pgvector-agnostic `readonly_connection()`/`db.py` boundary to
  vector-specific setup for every connection, not just the two query
  functions that actually need it — the literal+`CAST` approach keeps that
  coupling local to `vector_search.py`.
- **Registering `search_similar_campaigns` as an LLM-callable tool now**,
  even though nothing calls it yet. Rejected: speculative — Phase 5 owns
  the decision of exactly how campaign generation retrieves its few-shot
  examples (direct call vs. tool call), and registering it prematurely
  would mean either guessing at that design now or shipping a tool the
  model can call with no real campaign-generation flow behind it yet.
- **An ANN index from the start**, reasoning "it's cheap insurance."
  Rejected: it isn't free — index build time, storage, and the
  approximate/exact trade-off are real costs with no corresponding benefit
  at ~150 total vectors; add it if/when the data volume actually warrants it.
