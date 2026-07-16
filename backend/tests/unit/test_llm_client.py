from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors, types

from app.agent.exceptions import AgentUnavailableError
from app.agent.llm_client import (
    FinalAnswer,
    GeminiClient,
    ModelToolCalls,
    TextChunk,
    ToolCallRequest,
    UserText,
)
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(
        database_url="postgresql+asyncpg://x:y@localhost/db",
        google_application_credentials="/path/to/key.json",
        gcp_project_id="ask-sous-dev",
        gcp_region="us-central1",
        readonly_db_password="pw",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_gemini_client_constructs_vertex_client_from_settings():
    settings = _settings(gcp_project_id="my-project", gcp_region="europe-west1")

    with patch("app.agent.llm_client.genai.Client") as mock_client_cls:
        GeminiClient(settings=settings)

    mock_client_cls.assert_called_once_with(
        vertexai=True, project="my-project", location="europe-west1"
    )


async def test_generate_turn_translates_function_call_response():
    function_call = types.FunctionCall(name="get_revenue_summary", args={"restaurant_id": "abc"})
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(function_call=function_call)])
            )
        ]
    )

    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.generate_content = MagicMock(return_value=response)

    result = await client.generate_turn(history=[UserText("what was my revenue?")], tools=[])

    assert result == [ToolCallRequest(name="get_revenue_summary", args={"restaurant_id": "abc"})]


async def test_generate_turn_translates_text_response_to_final_answer():
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text="Revenue was $1,234.")])
            )
        ]
    )

    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.generate_content = MagicMock(return_value=response)

    result = await client.generate_turn(history=[UserText("what was my revenue?")], tools=[])

    assert result == FinalAnswer(text="Revenue was $1,234.")


async def test_generate_turn_translates_api_error_to_agent_unavailable():
    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    api_error = errors.APIError(code=503, response_json={"error": {"message": "unavailable"}})
    client._client.models.generate_content = MagicMock(side_effect=api_error)

    with pytest.raises(AgentUnavailableError) as exc_info:
        await client.generate_turn(history=[UserText("hi")], tools=[])

    assert exc_info.value.__cause__ is api_error


def _text_chunk_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))
        ]
    )


async def test_generate_turn_stream_yields_text_chunks_then_final_answer():
    chunks = [
        _text_chunk_response("Revenue "),
        _text_chunk_response("was $1,234."),
    ]
    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.generate_content_stream = MagicMock(return_value=iter(chunks))

    events = [
        event
        async for event in client.generate_turn_stream(
            history=[UserText("what was my revenue?")], tools=[]
        )
    ]

    assert events == [
        TextChunk(text="Revenue "),
        TextChunk(text="was $1,234."),
        FinalAnswer(text="Revenue was $1,234."),
    ]


async def test_generate_turn_stream_yields_no_chunks_for_tool_call_response():
    function_call = types.FunctionCall(name="get_revenue_summary", args={"restaurant_id": "abc"})
    chunk = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(function_call=function_call)])
            )
        ]
    )
    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.generate_content_stream = MagicMock(return_value=iter([chunk]))

    events = [
        event
        async for event in client.generate_turn_stream(
            history=[UserText("what was my revenue?")], tools=[]
        )
    ]

    assert events == [
        ModelToolCalls(
            calls=[ToolCallRequest(name="get_revenue_summary", args={"restaurant_id": "abc"})]
        )
    ]


async def test_generate_turn_stream_translates_mid_stream_error_to_agent_unavailable():
    def failing_stream():
        yield _text_chunk_response("partial")
        raise errors.APIError(code=503, response_json={"error": {"message": "unavailable"}})

    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.generate_content_stream = MagicMock(return_value=failing_stream())

    collected = []
    with pytest.raises(AgentUnavailableError):
        async for event in client.generate_turn_stream(history=[UserText("hi")], tools=[]):
            collected.append(event)

    assert collected == [TextChunk(text="partial")]
