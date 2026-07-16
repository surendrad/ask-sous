# Phase 6: Frontend — Implementation Plan

**Date:** 2026-07-16
**Status:** Complete
**Source:** implementation-plan.md Phase 6

---

## Goal

The demoable product: a real UI wrapping everything built in Phases 1–5, applying the `/designer` output (`docs/definition/design-guidelines.md`, already implemented as CSS tokens in Phase 0's `frontend/src/index.css`) to three views — a chat interface with genuinely streamed responses, a restaurant switcher, and a campaigns panel — composed into the split-view layout the design guidelines specify (`docs/definition/design-guidelines.md` §5: 224px sidebar + chat/campaigns split).

**Streaming decision (confirmed with the user before this plan was written):** implementation-plan.md 6.1 and `stack.md` both call for real token-by-token streaming, not a simulated typewriter effect over a single JSON response — and the Risk Register already anticipates this ("log the full assembled response server-side after the stream completes, not just what's sent to the client"). This phase therefore includes real backend work, not just frontend: `/chat` becomes a Server-Sent-Events endpoint, and `GeminiClient` gains a streaming call path. This is the one place this phase reaches back into `backend/`.

Same live-credentials caveat as every prior phase: the SSE plumbing itself, and every layer above the SDK boundary, is fully testable against fixture/mocked streaming responses. Whether a *real* Gemini streaming call actually produces smooth, real-time chunks over the network can only be verified once `docs/reference/gcp-setup.md` is completed — tracked as a UAT item requiring live credentials, same pattern as Phases 3–5.

## Prerequisites

- Phases 3 and 5 complete: `answer_question()`, `/chat`, `/campaigns`, `GeminiClient`/`llm_client.py` all in place and passing.
- `/designer` already run: `docs/definition/design-guidelines.md` and `docs/definition/design-system.html` exist; Phase 0 already applied the full token set to `frontend/src/index.css` and Tailwind's `@theme` block — confirmed via direct read, no work needed there.
- Phase 0's frontend shell (`frontend/src/App.tsx`, `HealthCheckPage.tsx`, `lib/api.ts`, `lib/theme.ts`, TanStack Query, shadcn/ui `Button`, Lucide icons) is in place and will be built on, not replaced. `HealthCheckPage` is retired as the app's root once real views exist (kept as a component, or deleted — decide during implementation based on whether a "backend unreachable" state still needs it).
- Backend venv active, frontend `npm install` run, local Postgres running + seeded.

## Implementation Details

### 6.0 Backend: real streaming for `/chat`

**`GeminiClient.generate_turn_stream()`** (`backend/app/agent/llm_client.py`) — a second entry point alongside the existing `generate_turn()` (which stays, unchanged, since `campaigns.py`'s single-shot generation doesn't need streaming and there's no reason to force it through a stream). Calls the SDK's `models.generate_content_stream()` (confirmed present on the installed `google-genai` version — synchronous `Iterator[GenerateContentResponse]`, not an async iterator) instead of `generate_content()`.

Because the SDK's stream is a **synchronous** iterator, bridge it to an async generator via a background thread + `asyncio.Queue` (a standard pattern for wrapping blocking iterators — the same reason `generate_turn()` already uses `asyncio.to_thread()` for the single blocking call). A small private helper, `_iter_in_thread()`, does this generically:

```python
async def _iter_in_thread(sync_iterable: Iterable[T]) -> AsyncIterator[T]:
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    _DONE = object()

    def worker() -> None:
        try:
            for item in sync_iterable:
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:  # re-raised on the consumer side, not swallowed
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    threading.Thread(target=worker, daemon=True).start()
    while (item := await queue.get()) is not _DONE:
        if isinstance(item, Exception):
            raise item
        yield item
```

`generate_turn_stream()` iterates the bridged stream, and for each `GenerateContentResponse` chunk inspects its parts exactly like `_translate()` already does: a `function_call` part is accumulated into a `list[ToolCallRequest]`; a `text` part is both accumulated (to build the full final answer for logging) **and yielded immediately** as a new `TextChunk(text: str)` dataclass, so the caller can forward it to the client the instant it arrives. After the stream ends: if any tool calls were seen, yield a final `ModelToolCalls(calls=...)` event (reusing the existing dataclass — a tool-calling round produces no visible text, so nothing was streamed to the client for that round, only the tool-call resolution itself matters); otherwise yield a final `FinalAnswer(text=full_text)` event (reusing the existing dataclass) so the caller has an unambiguous "this round is a completed answer, not tool calls" signal without needing to track accumulation state itself. Same `AgentUnavailableError` translation as `generate_turn()` for any SDK-level failure raised either at call-start or mid-stream (the bridging helper's re-raise makes a mid-stream failure surface at the `await queue.get()` call site, inside the same `try`).

**`answer_question_stream()`** (`backend/app/agent/insights.py`) — an async generator alongside the existing `answer_question()` (kept for `campaigns.py`... no, `campaigns.py` uses `generate_turn()` directly, not `answer_question()` — kept because it's still the simplest, most-tested path for any future non-streaming caller, e.g. a CLI script or a future batch/eval harness). Same orchestration loop and model-routing logic as `answer_question()`, but calls `client.generate_turn_stream()` per round instead of `generate_turn()`, and yields `TextChunk` events straight through to its own caller as they arrive from a final-answer round. Tool-calling rounds are resolved internally exactly as before (same `_run_tool_call()`, same `asyncio.gather()`, same audit logging per round) — nothing about tool dispatch changes, only how the *final* round's text reaches the caller. At the end (after the loop's final `TextChunk`s are exhausted for the answer-producing round), yields one last event carrying the complete `AgentTurnResult` (reusing the existing dataclass) so the caller can log `agent_turn_completed` and build the tool-call summary the same way `answer_question()` does today — this is the concrete implementation of the Risk Register's "log the full assembled response server-side after the stream completes."

Given the amount of logic shared between `answer_question()` and `answer_question_stream()` (the round loop, model routing, tool dispatch, per-round logging), evaluate during implementation whether to factor the round-loop body into a shared internal helper parameterized by "how do I get this round's output" (`generate_turn` vs `generate_turn_stream`) rather than maintaining two near-duplicate loops — this is exactly the kind of duplication `/simplify`'s reuse pass would flag, so it's worth doing proactively rather than waiting to be told. Decide the concrete shape once both are written and the actual overlap is visible, rather than guessing the abstraction up front.

**`POST /chat` becomes an SSE endpoint** (`backend/app/api/chat.py`) — returns `StreamingResponse(media_type="text/event-stream")`. Each event is a `data: {...}\n\n` line, JSON-encoded, with an explicit `type` field: `{"type": "text_chunk", "text": "..."}` for each streamed token/chunk, and a final `{"type": "done", "answer": "...", "tool_calls": [...], "model": "..."}` carrying exactly the same shape `ChatResponseData` returns today (so the frontend's final-state handling is a straightforward superset of the old single-response shape, not a new contract). The restaurant-existence 404 check stays a normal, non-streamed JSON response — no reason to open an SSE stream just to immediately error. `AgentUnavailableError`/`AgentIncompleteError` raised **before** the first byte is sent still go through the existing exception handlers (503/502 JSON); a failure **mid-stream** (after some chunks have already reached the client) is sent as a final `{"type": "error", "message": ..., "code": ...}` SSE event instead, since the HTTP status/headers are already committed once streaming has started — this asymmetry is an inherent SSE constraint, not a design choice, and gets called out explicitly in `docs/decisions/011-sse-streaming-and-mid-stream-errors.md`.

**`GET /restaurants`** (new, small — `backend/app/api/restaurants.py`) — implementation-plan.md's Phase 6 doesn't call this out explicitly, but 6.2's restaurant switcher needs a list of the five seeded restaurants (id + name, at minimum) from somewhere, and nothing in Phases 0–5 exposes one. A single read-only query (`SELECT id, name FROM restaurants ORDER BY name`) via `readonly_connection()`, returned inside the standard envelope. Registered in `main.py` alongside the other routers.

**Tasks (red-green-refactor):**
- [ ] Write a failing unit test for `_iter_in_thread()` — a plain sync generator (no SDK involved) bridged to async, asserting items arrive in order and a raised exception mid-iteration propagates to the consumer
- [ ] Implement `_iter_in_thread()`
- [ ] Write a failing unit test for `GeminiClient.generate_turn_stream()` — a hand-built sequence of real `GenerateContentResponse` chunks (text-only, no network) yields matching `TextChunk` events in order, followed by a final `FinalAnswer` event with the concatenated text
- [ ] Write a failing unit test for the tool-call case — chunks containing a `function_call` part yield no `TextChunk` events, followed by a final `ModelToolCalls` event
- [ ] Write a failing unit test asserting an SDK error raised mid-stream is translated to `AgentUnavailableError`
- [ ] Implement `generate_turn_stream()`
- [ ] Write failing unit tests for `answer_question_stream()` (mocked `GeminiClient.generate_turn_stream`) mirroring `test_insights_loop.py`'s coverage: single-round final answer streams `TextChunk`s then a completion event; multi-round tool-calling still resolves tools and logs exactly as `answer_question()` does; round cap still raises `AgentIncompleteError`
- [ ] Implement `answer_question_stream()`, factoring out shared loop logic with `answer_question()` if the duplication is real once both exist
- [ ] Write a failing integration test driving `POST /chat` end-to-end with a mocked streaming `GeminiClient`, asserting the raw SSE response body contains ordered `text_chunk` events followed by a `done` event with the right shape
- [ ] Write a failing integration test for the mid-stream-failure path — asserts a final `error` SSE event, not a raw exception/broken connection
- [ ] Implement the SSE endpoint
- [ ] Write a failing integration test for `GET /restaurants` (5 seeded restaurants, correct shape, sorted by name)
- [ ] Implement `GET /restaurants`
- [ ] Write `docs/decisions/011-sse-streaming-and-mid-stream-errors.md`

### 6.1 Chat interface

`frontend/src/lib/api.ts` gains `streamChat(restaurantId, question, { onChunk, onDone, onError })` — wraps `fetch()` with a `ReadableStream` reader parsing `data: ...\n\n` frames (native `EventSource` doesn't support POST bodies, so this is a manual SSE-over-fetch parser, not `EventSource`) rather than a full SSE client library — the frame format is simple enough (one JSON object per `data:` line) that a dependency isn't justified.

New `frontend/src/pages/ChatPage.tsx` (or `ChatView.tsx`, named consistently with whatever the sidebar nav ends up calling it) implementing design-guidelines.md §11's chat pattern: message list (user messages right-aligned brand-filled bubbles, agent messages left-aligned `elevated` bubbles), inline citation chips under any agent message backed by tool calls (the frontend's own visible expression of the "no naked numbers" rule — every numeric claim shows its tool-call receipt), a three-dot bounce "thinking" indicator (design-guidelines.md §10) while waiting for the first chunk, and an input bar pinned to the bottom. Streamed text renders incrementally as `text_chunk` events arrive (this is now literal, not simulated) with the blinking-cursor treatment design-guidelines.md §10 specifies while a message is still streaming.

`frontend/src/components/` additions: `ChatMessage.tsx` (user/agent bubble variants), `CitationChip.tsx` (design-guidelines.md's info-wash token, distinct from any brand-colored "AI generated" styling), `ThinkingIndicator.tsx`.

**Tasks (red-green-refactor):**
- [ ] Write a failing Vitest test for the SSE-over-fetch parser in `api.ts` (mocked `fetch` returning a `ReadableStream` of encoded SSE frames) asserting `onChunk`/`onDone`/`onError` fire correctly and in order
- [ ] Implement `streamChat()`
- [ ] Write failing RTL component tests for `ChatMessage`, `CitationChip`, `ThinkingIndicator` (rendering, variant props)
- [ ] Implement those components
- [ ] Write failing RTL tests for `ChatPage`: submitting a question renders the thinking indicator, then streamed chunks appended incrementally, then citation chips once `tool_calls` are known, using a mocked `streamChat`
- [ ] Implement `ChatPage`

### 6.2 Restaurant switcher

`frontend/src/lib/api.ts` gains `getRestaurants()`. A React Context (`frontend/src/lib/restaurant-context.tsx`, per design-guidelines.md's "React Context for UI-only state" convention already noted in `CLAUDE.md`) holds the currently-selected restaurant id, defaulting to the first restaurant once the list loads, and is read by both the chat page (to scope `/chat` requests) and the campaigns panel (to scope `/campaigns` requests) — this is the single source of truth the design guidelines describe as "purely a data-context switch."

`frontend/src/components/RestaurantSwitcher.tsx` — dropdown-menu pattern per design-guidelines.md §8, lives at the top of the sidebar per §11.

**Tasks (red-green-refactor):**
- [ ] Write a failing Vitest test for `getRestaurants()`
- [ ] Implement it
- [ ] Write failing tests for the restaurant context (default selection, switching updates consumers)
- [ ] Implement the context
- [ ] Write failing RTL tests for `RestaurantSwitcher` (renders options, selecting one updates context, keyboard-navigable per accessibility requirements)
- [ ] Implement `RestaurantSwitcher`

### 6.3 Campaigns panel

`frontend/src/lib/api.ts` gains `generateCampaign(restaurantId, brief)` (plain request/response — `/campaigns` was deliberately not made streaming in Phase 5/6, since campaign copy is short and the "watch it appear" value is lower than chat's; confirm this reads correctly in `docs/decisions/011` or note it as an explicit non-goal to avoid it reading as an oversight).

`frontend/src/pages/CampaignsPanel.tsx` (right panel in the split view per design-guidelines.md §5/§11): a brief input, a "Generate" action, and stacked campaign-draft cards (channel tag, copy preview, Regenerate + Copy-to-clipboard actions) with the card-hover and regenerate-pulse motion treatments from §10. A dashed-border empty-state card (§8) when no draft exists yet.

**Tasks (red-green-refactor):**
- [ ] Write a failing Vitest test for `generateCampaign()`
- [ ] Implement it
- [ ] Write failing RTL tests for `CampaignsPanel`: empty state renders, submitting a brief shows a loading state then a populated card, Regenerate re-calls the API, Copy writes to the clipboard (mock `navigator.clipboard`)
- [ ] Implement `CampaignsPanel`

### 6.4 App shell and design system application

`frontend/src/components/AppShell.tsx` — the 224px sidebar (brand mark, `RestaurantSwitcher`, nav items Chat/Campaigns, footer status line) + the `grid-template-columns: 224px 1.6fr 1fr` split view per design-guidelines.md §5, collapsing to a bottom tab bar below ~768px. `App.tsx` is rewritten to mount `AppShell` (wrapping `ChatPage` + `CampaignsPanel`) as the real root, replacing `HealthCheckPage` as the default view — `HealthCheckPage` itself stays in the codebase (still useful as a manual "is the backend up" check) but is no longer what loads at `/`.

Dashboard view (implementation-plan.md 6.x doesn't list it under Phase 6's numbered sub-sections, and design-guidelines.md §11 explicitly frames it as Phase-7-adjacent nice-to-have) is **out of scope for this phase** — the sidebar nav item for it can exist as a disabled/"coming soon" placeholder rather than a working route, consistent with implementation-plan.md's own MVP framing (Phase 7 is where dashboard charts are built).

**Tasks:**
- [ ] Write failing RTL tests for `AppShell` (renders sidebar nav, active-state styling, mobile breakpoint collapses to tab bar — jsdom viewport mocking or a CSS-class-presence assertion rather than true responsive rendering)
- [ ] Implement `AppShell`
- [ ] Wire `App.tsx` to mount it
- [ ] Manual pass: open the app in a real browser, compare against `docs/definition/design-system.html` for token/component fidelity

## Testing

### Integration Tests
- [ ] Backend: full SSE round-trip through `/chat` with mocked streaming `GeminiClient`, real tool dispatch, real logging
- [ ] Backend: `/restaurants` returns all 5 seeded restaurants

### Manual Verification
- [ ] Ask a question in the running app, watch the answer stream in token-by-token against the real (mocked, since no live credentials) backend
- [ ] Switch restaurants, confirm chat and campaigns both re-scope
- [ ] Generate a campaign, regenerate it, copy it
- [ ] Toggle OS dark/light mode, confirm the app follows it (no in-app toggle built yet, per Phase 0's `theme.ts` comment — out of scope here too, unless it turns out to be nearly free once the shell exists)
- [ ] Resize to mobile width, confirm the bottom-tab-bar collapse

## User Acceptance Tests

- [ ] UAT-6.1: Owner asks a question and watches the answer stream in, with citation chips appearing after
- [ ] UAT-6.2: Owner switches restaurants and sees chat/campaigns scope change accordingly
- [ ] UAT-6.3: Owner generates a campaign draft, regenerates it, and copies it
- [ ] UAT-6.4: A backend outage mid-stream surfaces a clear error in the chat UI rather than a silent hang — **requires live credentials or a forced failure injection to observe the real mid-stream path**
- [ ] UAT-6.5: The app is usable on a mobile-width viewport (bottom tab bar, single-column views)

## Documentation Updates

- [ ] `docs/decisions/011-sse-streaming-and-mid-stream-errors.md`
- [ ] Update `docs/tasks.md` with Phase 6 tasks
- [ ] Update `docs/uat.md` with UAT-6.1–6.5
- [ ] Update `docs/changelog.md` with Phase 6 completion
- [ ] Update `CLAUDE.md`: new `/restaurants` endpoint, SSE `/chat` contract change (breaking — the response shape moves from single JSON to an event stream; note this explicitly since it affects anyone testing `/chat` with `curl` the old way), frontend structure
- [ ] Update `docs/definition/implementation-plan.md` to mark Phase 6 status

## Security Considerations

No new security-relevant surface beyond what SSE itself implies: the stream still goes through the same restaurant-scoping and read-only DB boundary as before. CORS is already scoped to `http://localhost:5173` (Phase 0); no change needed for SSE specifically. No new secrets or auth surface — same "no user accounts" framing as every prior phase.

## Dependencies & Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Real Vertex AI streaming behavior (chunk granularity, latency) differs from what fixture-built chunks assume | Medium | Medium | Fixture tests prove the plumbing; UAT-6.1/6.4 explicitly flagged as needing live credentials to fully verify |
| Thread-per-stream bridging (`_iter_in_thread`) adds a new concurrency pattern not used elsewhere in the codebase | Low | Low | Contained entirely inside `llm_client.py`; documented in ADR-011 with the reasoning (sync SDK iterator, no async streaming API available) |
| Manual SSE-over-fetch parsing on the frontend (no `EventSource`, since it can't send a POST body) is more code than a library would be | Low | Low | The frame format is trivial (`data: {...}\n\n`); a full SSE client library is unjustified overhead for one endpoint |
| Scope creep: this phase now includes real backend streaming work in addition to three full frontend views | Medium | Medium | Explicitly surfaced to and confirmed with the user before this plan was written, rather than discovered mid-implementation |
