# ADR-008: Embedding Model and Client Adapter

**Date:** 2026-07-16
**Status:** Accepted

## Context

Phase 4 needs to generate vector embeddings for `reviews.review_text` and
`campaigns.copy_text` so they're searchable via pgvector. ADR-003 already
fixed both embedding columns at `vector(768)`, on the assumption that
`text-embedding-004` (Google's `768`-dimensional Vertex AI embedding model)
would be used, while leaving the door open to `gemini-embedding-001`
truncated to `768` via `output_dimensionality` if that turned out to be the
better choice. As with Phase 3's Gemini model selection (ADR-007), no live
Vertex AI credentials exist in this environment, so the exact model choice
can't be verified against a real API call at build time.

## Decision

**Model:** `text-embedding-004` (the `EMBEDDING_MODEL` constant in
`app/agent/embedding_client.py`), matching ADR-003's stated assumption —
the simpler, purpose-built embedding model over `gemini-embedding-001`
truncated down, since there's no other reason in this project to prefer
the newer general-purpose model over the one the column dimensionality was
already chosen around. **Not verified against a live Vertex AI model
listing in this environment** — same open item as ADR-007's Flash-model-ID
caveat: confirm the exact model ID is still current once live credentials
exist, before UAT-4.4/4.5 are attempted, and update this ADR if it has
moved.

**Client adapter:** a second, narrowly-scoped adapter, `EmbeddingClient`
(`app/agent/embedding_client.py`), alongside `GeminiClient` — not merged
into it. `EmbeddingClient` and `GeminiClient` are the only two modules
anywhere in `app/agent/`/`app/api/` permitted to import `google.genai`.
`EmbeddingClient.embed_texts(texts: list[str]) -> list[list[float]]` is the
entire public surface: plain Python types in and out, no SDK objects
crossing the boundary, mirroring `GeminiClient.generate_turn()`'s pattern
exactly. This is what makes the fixture/mock-based testability story from
ADR-007 apply here too: every layer above the adapter (`vector_search.py`,
`tool_registry.py`, `embed_seed_data.py`) is tested via `AsyncMock`
returning plain `list[list[float]]`, and only `embedding_client.py`'s own
tests construct real (network-free) `google.genai.types` response objects.

**Two adapters, not one, because the two SDK calls (`generate_content` vs.
`embed_content`) have unrelated request/response shapes and unrelated
call sites** — `GeminiClient` is only ever used from the orchestration loop
(`insights.py`), `EmbeddingClient` is only ever used from
`vector_search.py` and `embed_seed_data.py`. Merging them into one class
would couple two independent concerns behind a single interface for no
benefit; keeping them separate keeps each adapter's public surface small
and its own test file focused on one SDK call shape.

**Dimension validation as a first-class step, not an afterthought:**
`_validate_dimensions()` raises `ValueError` naming the offending index if
any returned vector isn't exactly `768` elements — the DB column is
`vector(768)` and would otherwise reject a mismatched insert with a less
diagnosable Postgres-level error. Checking in the adapter, before the
caller ever tries to write to the DB, surfaces a model-configuration
mistake (e.g. accidentally calling `gemini-embedding-001` without
`output_dimensionality=768`) immediately and clearly.

**Auth/credential failures translate to `AgentUnavailableError` too, not
just API-level errors.** During implementation, `embed_seed_data.py` was
manually run against this environment's placeholder credentials and
produced a raw, unhandled `google.auth.exceptions.DefaultCredentialsError`
stack trace instead of failing through the domain exception path — the
original `except (errors.APIError, errors.ClientError, errors.ServerError)`
clause (mirrored from `GeminiClient`) didn't catch it, since credential
loading happens beneath the SDK's own HTTP-error handling. Fixed in both
`EmbeddingClient.embed_texts()` and `GeminiClient.generate_turn()` by also
catching `google.auth.exceptions.GoogleAuthError` (the base class covering
`DefaultCredentialsError` and every other auth failure mode). This is the
correct fix in both adapters, not just this phase's new one, since the same
placeholder-credentials gap existed in `GeminiClient` from Phase 3 onward
and simply hadn't been exercised by a real script run yet.

## Consequences

- Adding embeddings required zero changes to the `EmbeddingClient`'s
  callers' testing strategy — `vector_search.py` and `embed_seed_data.py`
  were both written and fully tested (unit + integration, against the real
  seeded database with hand-crafted/mocked vectors) with zero live GCP
  access, exactly as Phase 3's tool layer was.
- The real Vertex AI embedding call itself remains unverified until live
  credentials exist (UAT-4.4/4.5) — mocked tests prove the plumbing is
  correct, not that a real `text-embedding-004` call actually returns
  useful, `768`-dimensional embeddings for this app's text.
- Running `embed_seed_data.py` against this environment's current
  placeholder `.env` now fails cleanly with a domain-specific
  `AgentUnavailableError`, not a raw unrelated stack trace — verified
  manually as part of this phase's Testing tasks.

## Alternatives Considered

- **Merging embedding calls into `GeminiClient`** (e.g. a
  `GeminiClient.embed_texts()` method alongside `generate_turn()`).
  Rejected: couples two independent SDK call shapes and call sites behind
  one class for no benefit, and would force every `GeminiClient` test
  fixture to also account for embedding-shaped SDK objects it never uses.
- **`gemini-embedding-001` as the default model.** Rejected: no concrete
  reason to prefer it over `text-embedding-004` in this project — it would
  require `output_dimensionality=768` to match the existing column, adding
  a config knob with no corresponding benefit, since nothing in this
  project needs the newer model's other capabilities (larger native
  dimensionality, task-type tuning beyond what's needed here).
- **Skipping dimension validation and trusting the DB to reject bad
  writes.** Rejected: a Postgres-level dimension mismatch error is far less
  diagnosable ("vector must have 768 dimensions" with no indication of
  which text/model call produced the bad vector) than failing immediately
  in the adapter with the specific index and count that's wrong.
