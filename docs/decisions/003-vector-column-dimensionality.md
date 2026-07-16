# ADR-003: Vector Column Dimensionality

**Date:** 2026-07-15
**Status:** Accepted

## Context

Phase 1 creates `reviews.embedding` and `campaigns.embedding` as `pgvector` `vector` columns, but the embedding model that will actually populate them isn't chosen until Phase 4. `pgvector`'s `vector(N)` type requires a fixed dimension `N` at column-creation time — leaving it unspecified isn't an option, so a dimensionality has to be picked now, ahead of the model decision.

## Decision

Both embedding columns are created as `vector(768)`, matching Google's `text-embedding-004` — the most likely default per `docs/definition/stack.md`'s open TBD note on the exact Vertex AI embedding model. If Phase 4 instead selects `gemini-embedding-001` (whose native output is larger), that model also supports an `output_dimensionality` parameter that can truncate its output to 768, so the column choice doesn't force a specific model — it just sets the target dimension either model can be configured to produce.

Both columns are nullable and populated by no code until Phase 4, so this choice carries no immediate data-migration risk.

## Consequences

- Easier: the schema is fully defined now, in Phase 1, rather than blocked on a Phase 4 decision that hasn't been made yet.
- Harder (low-impact): if Phase 4 ends up needing a different dimension after all, a follow-up migration (`ALTER COLUMN embedding TYPE vector(N)`) is needed — cheap, since both columns are still entirely `NULL` at that point.

## Alternatives Considered

- **Defer the columns entirely to Phase 4** — rejected. It would mean Phase 1's schema migration doesn't match master-plan.md §3's entity definitions (both `reviews` and `campaigns` list an embedding field), and every later phase's "full schema exists" assumption would be wrong until Phase 4.
- **A generic, unconstrained `vector` column (no fixed dimension)** — rejected. `pgvector` supports this, but it disables dimension-mismatch protection at insert time and prevents building an ANN index later (`ivfflat`/`hnsw` indexes require a fixed dimension) — not worth the flexibility for a column whose dimension is going to be fixed the moment Phase 4 picks a model anyway.
