# ADR-010: Model Routing Heuristic

**Date:** 2026-07-16
**Status:** Accepted

## Context

Implementation-plan.md's Phase 5 goal explicitly calls for "model routing
demonstrating the fast/cheap-default-escalate-when-it-matters pattern":
campaign requests always route to the Pro-tier model; insights questions
route to Flash 2.5 by default, escalating when a query requires 3+ tool
calls or the user explicitly asks for deeper analysis. This needed two
concrete decisions this phase actually had to make: the exact Pro-tier
model ID (ADR-007 deferred this explicitly), and exact, testable escalation
thresholds rather than a vague "when it matters."

## Decision

**Pro-tier model:** `gemini-2.5-pro` (the `PRO_MODEL` constant in
`app/agent/llm_client.py`). Same caveat as ADR-007's `FLASH_MODEL`: not
verified against a live Vertex AI model listing in this environment —
confirm before UAT-5.5/5.6/UAT-3.5/3.6 are attempted.

**Campaign generation always uses `PRO_MODEL`, unconditionally** — there is
no routing decision to make in `app/agent/campaigns.py`, matching
implementation-plan.md 5.2's "campaign requests always route to the
Pro-tier model" verbatim. Campaign copy is a single, low-frequency,
externally-visible generation (an owner sends this to their customers), so
correctness and tone-matching quality matter more than the marginal cost
difference — unlike insights Q&A, which is asked far more often and mostly
needs simple, cheap lookups.

**Insights routing heuristic** (`_select_model()` in `app/agent/insights.py`):

```python
ESCALATION_TOOL_CALL_THRESHOLD = 3
_DEEPER_ANALYSIS_KEYWORDS = ("deep dive", "deeper analysis", "thorough", "in depth", "in-depth")

def _select_model(question: str, *, completed_tool_call_rounds: int) -> tuple[str, str]:
    if any(keyword in question.lower() for keyword in _DEEPER_ANALYSIS_KEYWORDS):
        return PRO_MODEL, "keyword"
    if completed_tool_call_rounds >= ESCALATION_TOOL_CALL_THRESHOLD:
        return PRO_MODEL, "tool_call_threshold"
    return FLASH_MODEL, "default"
```

Evaluated at the top of every round in `answer_question()`'s loop (not once
per turn) — a turn can start on Flash and escalate to Pro mid-turn once it's
already needed 3 rounds without reaching a final answer, which is exactly
the "query requires 3+ tool calls" signal from the phase goal. The keyword
check takes priority over the round count and can escalate a turn to Pro
from round 0, before any tool call has even happened, for an explicit "give
me a deep dive on X" request. The chosen `(model, routing_reason)` is logged
on every `agent_turn_model_selected` event, and `AgentTurnResult.model`
reflects whichever model actually produced the final answer.

## Consequences

- The routing decision is fully unit-testable in isolation
  (`test_model_routing.py`) without touching `GeminiClient` at all, and
  separately covered end-to-end in `test_insights_loop.py` (a 4-round
  fixture conversation asserting the final `generate_turn()` call used
  `PRO_MODEL`) and `test_insights_logging.py` (asserting `routing_reason`
  is logged).
- The threshold (3) and keyword list are a first-pass heuristic, not tuned
  against real usage data — there is none yet, since this project has no
  production traffic. Both are simple module-level constants, deliberately
  easy to revisit once real question patterns are observed.
- A turn that escalates mid-way still incurs the cost of its earlier
  Flash-tier rounds — this is intentional; escalating "for the rest of a
  turn already in trouble" is cheaper than escalating a turn's entire
  history retroactively, and matches the phase goal's spirit of "don't pay
  for Pro unless the situation actually calls for it."

## Alternatives Considered

- **A single per-turn routing decision made once, before round 0**, based
  only on keyword matching (no tool-call-count escalation). Rejected: this
  can't express "the question looked simple but turned out to need real
  digging," which is exactly the scenario implementation-plan.md's "3+ tool
  calls" criterion is meant to catch — that fact is only knowable
  mid-turn, not up front.
- **Always escalating on any tool call at all** (threshold of 1). Rejected:
  almost every insights question needs at least one tool call (a single
  `get_revenue_summary` lookup), so this would make Flash the exception
  rather than the default, defeating the "fast/cheap default" framing the
  phase goal explicitly asks for.
- **A learned/ML-based router.** Rejected as far out of scope for this
  project's scale — a small, explicit, logged heuristic is exactly what
  implementation-plan.md 5.2 asks for ("simple, explicit heuristic"), and
  is trivially auditable from the structured logs alone.
