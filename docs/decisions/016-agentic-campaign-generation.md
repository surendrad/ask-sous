# ADR-016: Agentic Campaign Generation

**Date:** 2026-07-16
**Status:** Accepted

## Context

`generate_campaign()` (ADR from Phase 5) was a fixed retrieve-then-generate
turn: fetch the brand voice guide, retrieve up to two similar past
campaigns, then one `PRO_MODEL` call with `tools=[]` — the model could only
write text, never look anything up. This worked for tone-only briefs
("announce our new patio seating") but broke down the moment a brief
referenced a specific fact the model had no way to check — "build a
campaign for our slowest weekday" or "call out how well our last promo
did" — forcing the model to either guess a plausible-sounding number/day
(a direct violation of the project's no-naked-numbers/no-invented-claims
discipline, see CLAUDE.md's Agent/grounding section) or write something
generic enough to avoid the claim altogether, which defeats the point of
asking.

## Decision

`generate_campaign()` is now agentic, structured the same way
`answer_question()` is: the model is offered the full `INSIGHTS_TOOLS`
roster and runs a bounded tool-calling loop (same `MAX_TOOL_CALL_ROUNDS`,
same `_resolve_tool_call_round()`/`_check_grounding()` helpers, imported
from `insights.py` rather than reimplemented) until it returns a
`FinalAnswer` or the round cap is hit, in which case it raises the same
`AgentIncompleteError` insights Q&A does.

Brand voice and past-campaign retrieval **stay a fixed pre-fetch**, not a
tool call — that's about establishing tone before generation starts, not a
fact the model needs to decide whether to look up, and forcing it through
a tool call would only add latency and round-cap pressure for something
that's needed on every single brief.

A new tool, **`get_weekday_performance`**
(`app/agent/tools/weekday_performance.py`), was added and registered in
both the chat and campaign system instructions so "which day is slow" has
one authoritative code path instead of the model reasoning over raw daily
rows from `get_revenue_summary` itself — and so a "what's my slowest
weekday" chat question and a "build a campaign for my slowest weekday"
brief are guaranteed to agree, not just likely to, since both call the
same function.

The campaign system instruction now also includes the restaurant's id and
today's date directly in the prompt (`build_campaign_system_instruction()`
gained `restaurant_id` and an optional `today` override), since a
tool-calling model needs both to construct valid tool arguments — resolving
"last month" into concrete dates and supplying the right `restaurant_id` —
neither of which the fixed-turn version ever needed to give it.

Tool calls made during generation are returned on
`CampaignGenerationResult.tool_calls` and surfaced through `POST
/campaigns`'s response and `CampaignsPanel.tsx` as citation chips, reusing
the existing `CitationChip` component chat already uses — the same
grounding-transparency pattern, not a new one invented for this feature.

## Consequences

- Campaign copy can now reference real performance data ("Tuesdays are
  slow — 20% off dine-in!") without inventing it, closing the gap between
  what chat can ground and what campaigns can ground.
- A tone-only brief still resolves in a single round with zero tool
  calls — the system instruction explicitly tells the model no lookup is
  needed when the brief doesn't reference any specific fact, so simple
  briefs don't pay extra latency for a capability they don't use.
- `generate_campaign()` can now fail with `AgentIncompleteError` (502)
  the same way `answer_question()` can, which it never could before — an
  accepted tradeoff, not a bug, since the previous version's `tools=[]`
  contract-violation path was already an unhandled-exception (500) case
  and no better a user experience.
- `get_weekday_performance` reuses `get_revenue_summary()` rather than a
  fresh query, so it stays extremely cheap to add — a pure `_build_
  weekday_performance()` grouping function plus a thin async wrapper,
  matching the project's pure/impure split convention.

## Alternatives Considered

- **A separate, smaller tool roster for campaigns** (e.g. only
  `get_weekday_performance`, `get_revenue_summary`, `list_campaigns`/
  `get_campaign_performance`) instead of the full `INSIGHTS_TOOLS` list.
  Rejected: campaigns only ever runs single-restaurant (ADR-015 excludes it
  from the multi-restaurant pattern entirely), so the list-first tools
  (`compare_locations`, multi-restaurant `get_upsell_metrics`) are already
  unreachable in practice via the system instruction's guidance without
  needing a second, separately-maintained tool declaration list.
- **Making brand-voice/example retrieval itself a tool call**, for
  architectural symmetry with everything else the model can look up.
  Rejected: every brief needs it, so making it optional/model-decided only
  adds a guaranteed extra round-trip with no corresponding benefit — it's
  pre-fetched framing information, not evidence the model chooses to cite.
- **Keeping the fixed-turn design and hand-coding a couple of
  brief-specific lookups** (e.g. detect "slowest weekday" via keyword
  matching and inject the answer into the prompt). Rejected: brittle,
  doesn't generalize to the next fact type someone asks about, and
  duplicates exactly the kind of judgment call `answer_question()`'s
  tool-calling loop already handles generally.
