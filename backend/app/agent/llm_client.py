"""The only module in app/agent/ permitted to import google.genai directly.

Wraps the Vertex AI SDK behind GeminiClient, which accepts and returns only
the app's own frozen dataclasses (ToolDeclaration, UserText, ModelToolCalls,
ToolResultsTurn, ToolCallRequest, FinalAnswer) — never a raw SDK type.
Callers build tool schemas as plain JSON-schema dicts and conversation
history as these plain dataclasses; every layer above this adapter is
testable with plain AsyncMock fixtures and zero GCP dependency. Only this
module's own tests need to construct real (but network-free) SDK objects.
See docs/decisions/007-gemini-model-selection-and-client-adapter.md.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any

import structlog
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import errors, types

from app.agent.exceptions import AgentUnavailableError
from app.core.config import Settings, get_settings

logger = structlog.get_logger()

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"


async def _iter_in_thread[T](sync_iterable: Iterable[T]) -> AsyncIterator[T]:
    """Bridges a blocking/synchronous iterator (the SDK's streaming call
    returns one, not an async iterator) onto the event loop: a background
    thread pulls items and pushes them onto an asyncio.Queue, which this
    generator drains. A raised exception is pushed onto the queue too and
    re-raised on the consumer side, rather than crashing the worker thread
    silently."""
    queue: asyncio.Queue[Any] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    done = object()

    def worker() -> None:
        try:
            for item in sync_iterable:
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:  # noqa: BLE001 - re-raised on the consumer side below
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, done)

    threading.Thread(target=worker, daemon=True).start()
    while (item := await queue.get()) is not done:
        if isinstance(item, Exception):
            raise item
        yield item


@dataclass(frozen=True)
class ToolCallRequest:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalAnswer:
    text: str


@dataclass(frozen=True)
class TextChunk:
    """One piece of a streamed final answer — see GeminiClient.generate_turn_stream()."""

    text: str


@dataclass(frozen=True)
class ToolDeclaration:
    """A tool's function-calling schema, as a plain JSON-schema dict —
    never a google.genai.types.Schema, so tool_registry.py never needs to
    import google.genai."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserText:
    text: str


@dataclass(frozen=True)
class ModelToolCalls:
    calls: list[ToolCallRequest]


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class ToolResultsTurn:
    results: list[ToolResult]


ConversationEntry = UserText | ModelToolCalls | ToolResultsTurn


def _to_function_declaration(declaration: ToolDeclaration) -> types.FunctionDeclaration:
    # parameters_json_schema accepts our plain JSON-schema dict directly —
    # no need to hand-construct a types.Schema tree ourselves.
    return types.FunctionDeclaration(
        name=declaration.name,
        description=declaration.description,
        parameters_json_schema=declaration.parameters,
    )


def _build_config(
    tools: list[ToolDeclaration], system_instruction: str | None
) -> types.GenerateContentConfig:
    # A types.Tool with an empty function_declarations list is rejected by
    # the real API ("tools[0].tool_type: required one_of 'tool_type' must
    # have one initialized field") — only mocked tests ever exercised this
    # path, so it went unnoticed until a live call (campaigns.py always
    # calls generate_turn() with tools=[]) surfaced it. Omit `tools`
    # entirely from the config when there are none to send, rather than
    # sending an empty-but-present Tool object.
    if not tools:
        return types.GenerateContentConfig(system_instruction=system_instruction)
    return types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=[_to_function_declaration(t) for t in tools])],
        system_instruction=system_instruction,
    )


def _entry_to_content(entry: ConversationEntry) -> types.Content:
    if isinstance(entry, UserText):
        return types.Content(role="user", parts=[types.Part(text=entry.text)])
    if isinstance(entry, ModelToolCalls):
        parts = [
            types.Part(function_call=types.FunctionCall(name=call.name, args=call.args))
            for call in entry.calls
        ]
        return types.Content(role="model", parts=parts)
    if isinstance(entry, ToolResultsTurn):
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    name=result.tool_name,
                    response={"error": result.error}
                    if result.error is not None
                    else {"result": result.result},
                )
            )
            for result in entry.results
        ]
        return types.Content(role="user", parts=parts)
    raise TypeError(f"Unknown conversation entry type: {type(entry)!r}")


class GeminiClient:
    """Thin adapter over google.genai.Client, scoped to this app's needs."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._client = genai.Client(
            vertexai=True, project=settings.gcp_project_id, location=settings.gcp_region
        )

    async def generate_turn(
        self,
        *,
        history: list[ConversationEntry],
        tools: list[ToolDeclaration],
        system_instruction: str | None = None,
        model: str = FLASH_MODEL,
    ) -> list[ToolCallRequest] | FinalAnswer:
        contents = [_entry_to_content(entry) for entry in history]
        config = _build_config(tools, system_instruction)
        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )
        except (errors.APIError, errors.ClientError, errors.ServerError, GoogleAuthError) as exc:
            logger.error("gemini_call_failed", exc_info=exc)
            raise AgentUnavailableError("The agent is temporarily unavailable.") from exc

        return self._translate(response)

    def _translate(
        self, response: types.GenerateContentResponse
    ) -> list[ToolCallRequest] | FinalAnswer:
        parts = response.candidates[0].content.parts
        tool_calls = [
            ToolCallRequest(name=part.function_call.name, args=dict(part.function_call.args or {}))
            for part in parts
            if part.function_call is not None
        ]
        if tool_calls:
            return tool_calls

        text = "".join(part.text or "" for part in parts if part.text is not None)
        return FinalAnswer(text=text)

    async def generate_turn_stream(
        self,
        *,
        history: list[ConversationEntry],
        tools: list[ToolDeclaration],
        system_instruction: str | None = None,
        model: str = FLASH_MODEL,
    ) -> AsyncIterator[TextChunk | FinalAnswer | ModelToolCalls]:
        """Same round semantics as generate_turn(), but yields TextChunk
        events as a final-answer round's text arrives, instead of waiting
        for the whole response. Terminates with exactly one ModelToolCalls
        (a tool-calling round — no text was ever streamed for it) or one
        FinalAnswer (the concatenation of every TextChunk already yielded)."""
        contents = [_entry_to_content(entry) for entry in history]
        config = _build_config(tools, system_instruction)
        try:
            stream = await asyncio.to_thread(
                self._client.models.generate_content_stream,
                model=model,
                contents=contents,
                config=config,
            )

            tool_calls: list[ToolCallRequest] = []
            text_parts: list[str] = []
            async for chunk in _iter_in_thread(stream):
                parts = chunk.candidates[0].content.parts
                tool_calls.extend(
                    ToolCallRequest(
                        name=p.function_call.name, args=dict(p.function_call.args or {})
                    )
                    for p in parts
                    if p.function_call is not None
                )
                chunk_text = "".join(p.text or "" for p in parts if p.text is not None)
                if chunk_text:
                    text_parts.append(chunk_text)
                    yield TextChunk(text=chunk_text)
        except (errors.APIError, errors.ClientError, errors.ServerError, GoogleAuthError) as exc:
            logger.error("gemini_call_failed", exc_info=exc)
            raise AgentUnavailableError("The agent is temporarily unavailable.") from exc

        if tool_calls:
            yield ModelToolCalls(calls=tool_calls)
        else:
            yield FinalAnswer(text="".join(text_parts))
