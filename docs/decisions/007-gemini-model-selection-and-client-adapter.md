# ADR-007: Gemini Model Selection and Client Adapter

**Date:** 2026-07-16
**Status:** Accepted

## Context

Phase 3 needs to call Vertex AI's Gemini API for function-calling, but this
implementation environment has no live GCP credentials (`.env` still has
placeholder `GOOGLE_APPLICATION_CREDENTIALS`/`GCP_PROJECT_ID` values, and
`docs/reference/gcp-setup.md`'s checklist hasn't been run). Everything in
this phase needs to be buildable and testable without a network call to
Vertex AI, while still being ready to work correctly the moment real
credentials are added — and CLAUDE.md's "no naked numbers" and per-turn
audit-logging rules need every layer above the SDK call to be exercised by
tests, not just trusted to work.

## Decision

**Model:** `gemini-2.5-flash` (the `FLASH_MODEL` constant in
`app/agent/llm_client.py`), matching CLAUDE.md's "Gemini Flash 2.5 default"
tech-stack statement. This ID has **not** been verified against a live
Vertex AI model listing in this environment — implementation-plan.md's own
Risk Register already flags that reference Gemini model IDs may have moved
since interview prep. This is an open item: confirm the exact current
Flash-tier ID against the `google-genai` SDK's model listing once live
credentials exist, before UAT-3.5 is attempted, and update this ADR if it
has changed. Pro-tier model selection (for Phase 5's routing heuristic) is
explicitly out of scope for this phase — `agent_turn_model_selected` is
already logged every turn so Phase 5 has somewhere to log a real routing
decision to without a schema change, but the value is currently always
`FLASH_MODEL`.

**Client adapter:** `GeminiClient` (`app/agent/llm_client.py`) wraps
`google.genai.Client` and is the *only* module anywhere in `app/agent/` or
`app/api/` permitted to import `google.genai`. It accepts and returns only
this app's own frozen dataclasses:

- Input: `ToolDeclaration` (a plain JSON-schema dict, not `types.Schema`)
  and `ConversationEntry` (`UserText` / `ModelToolCalls` / `ToolResultsTurn`)
  — never a raw `types.Content`/`types.Tool`.
- Output: `list[ToolCallRequest]` or `FinalAnswer` — never a raw
  `types.GenerateContentResponse`.

`GeminiClient.generate_turn()` internally translates these plain dataclasses
to/from real `google.genai.types` objects. This means every layer above the
adapter — `tool_registry.py`, `insights.py`, and their tests — never touches
`google.genai` at all, and is fully testable with plain `AsyncMock` returning
the app's own dataclasses. Only `llm_client.py`'s own tests need to
construct real (but network-free) SDK objects: `google.genai` types can be
constructed directly without a network call or valid credentials (only
`.generate_content()` actually calls out), so `test_llm_client.py`'s
translation tests build real `GenerateContentResponse`/`Candidate`/`Content`/
`Part` objects and mock only the `generate_content` call itself.

## Consequences

- The entire test suite for Phase 3 runs with zero GCP dependency and zero
  network calls — `grep -rn "from google" app/agent/ app/api/` shows exactly
  one file (`llm_client.py`).
- If `google-genai`'s SDK surface changes in a future version, only
  `llm_client.py` needs to change — `tool_registry.py` and `insights.py`
  are insulated by the plain-dataclass boundary.
- The genuinely unverifiable gap: does a *real* Gemini Flash 2.5 call, with
  the *real* tool schemas this phase defines, actually produce sensible
  function calls and a sensible final answer? Mocked tests prove the
  plumbing is correct, not that the real model behaves as expected against
  these exact schemas. UAT-3.5/3.6 are scoped to close this gap once live
  credentials exist — this should be treated as an open item, not silently
  assumed to work because the mocked tests pass.
- Zero automatic retries on Vertex AI failure (`AgentUnavailableError`,
  caught and translated in `generate_turn()`) — CLAUDE.md's "never retried
  indefinitely" rule, satisfied by the simplest possible choice: a failed
  turn fails clearly, and the user can just ask again.

## Alternatives Considered

- **Passing raw `google.genai.types` objects through `tool_registry.py` and
  `insights.py`** (the phase's initial implementation, corrected during
  this phase's own build before code review). Rejected: this made the
  "mock at the adapter boundary" testing strategy false in practice — those
  modules imported `google.genai` directly, so any SDK-side type change
  would break them directly, not just the adapter, and their own tests
  would need SDK-shaped fixtures instead of plain dataclasses.
- **Introspecting Python type hints to auto-generate tool schemas** instead
  of hand-writing them. Rejected (matches implementation-plan.md's own
  framing): `UUID`/`date`/`Decimal` don't map cleanly to JSON Schema, and
  the four existing Phase 2 tools' signatures weren't designed with
  function-calling schema generation in mind.
- **Automatic retries with backoff on `AgentUnavailableError`.** Rejected:
  adds complexity with no clear benefit at this project's scale (a demo,
  not a production service under SLA pressure), and risks masking real
  outages behind a delay instead of surfacing them clearly.
