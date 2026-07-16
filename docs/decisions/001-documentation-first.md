# ADR-001: Documentation-First Development

**Date:** 2026-07-15
**Status:** Accepted

## Context

Ask Sous is a solo project whose entire purpose is to let its builder speak concretely, in an interview setting, about the real tradeoffs of building a grounded LLM agent — not just recall a design. That requires more than working code: it requires a clear, current record of *why* each decision was made, so those reasons are recallable months later without re-deriving them from the code itself. It also means correctness needs to be independently verifiable at every stage, not just asserted.

## Decision

The project follows a documentation-first approach, with these principles applied throughout:

1. **Architecture Decision Records (ADRs)** — every non-trivial technical or product decision is recorded in `docs/decisions/`, using the numbered template (`docs/decisions/_template.md`). This includes model/library choices left open in the implementation plan (e.g. exact embedding model, exact Pro-tier Gemini model, routing heuristic thresholds).
2. **Living documentation** — when a change affects an existing doc (master plan, implementation plan, stack reference), that doc is updated in the same changeset as the code, not left to drift.
3. **Plans before code** — every phase and feature is planned as a markdown document in `docs/plans/` before implementation begins, not written up after the fact.
4. **Changelog** — notable changes and phase completions are logged in `docs/changelog.md`.
5. **Tests before code (TDD)** — tests are written before the code they verify, following red-green-refactor. Exceptions: UI layout, configuration, and scaffolding, which are reasonably tested after the fact. Testing depth is **practical** project-wide, with the Phase 1 (Data Layer) and Phase 2 (Aggregation Tools) held to a stricter bar, since their correctness is the project's core success metric.

## Consequences

- Easier: revisiting the project after time away, explaining any decision under interview questioning, catching regressions in intent (not just in code) when requirements shift.
- Harder: slightly more overhead per change, since documentation updates are part of "done," not an afterthought.

## Alternatives Considered

- **Code-first, document later** — rejected. For a project whose value is explicitly the ability to explain tradeoffs afterward, deferred documentation tends to never happen, or happen inaccurately from memory.
- **Comments-only, no separate docs** — rejected. Comments explain *what*, not *why*, and don't capture decisions that span multiple files (e.g. the read-only DB boundary, which touches schema, tool implementation, and the seed script).
