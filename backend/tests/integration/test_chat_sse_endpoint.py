import json
import uuid

from httpx import ASGITransport, AsyncClient

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.agent.insights import AgentTurnComplete, AgentTurnResult, ToolCallRecord
from app.agent.llm_client import TextChunk
from app.main import app


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        assert frame.startswith("data: ")
        events.append(json.loads(frame[len("data: ") :]))
    return events


async def _happy_path_stream(restaurant_id, question):
    yield TextChunk(text="Revenue ")
    yield TextChunk(text="was $500.")
    yield AgentTurnComplete(
        AgentTurnResult(
            answer="Revenue was $500.",
            tool_calls=[
                ToolCallRecord(
                    tool_name="get_revenue_summary",
                    arguments={"restaurant_id": str(restaurant_id)},
                    result={"total_revenue": "500.00"},
                    error=None,
                )
            ],
            model="gemini-2.5-flash",
        )
    )


async def test_chat_sse_happy_path_streams_chunks_then_done(seeded_restaurants, monkeypatch):
    restaurant_id = next(iter(seeded_restaurants.values()))
    monkeypatch.setattr("app.api.chat.answer_question_stream", _happy_path_stream)

    async with await _client() as client:
        response = await client.post(
            "/chat",
            json={"restaurant_id": str(restaurant_id), "question": "how much did I make?"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)

    assert events[0] == {"type": "text_chunk", "text": "Revenue "}
    assert events[1] == {"type": "text_chunk", "text": "was $500."}
    assert events[2]["type"] == "done"
    assert events[2]["answer"] == "Revenue was $500."
    assert events[2]["model"] == "gemini-2.5-flash"
    assert events[2]["tool_calls"][0]["tool_name"] == "get_revenue_summary"


async def test_chat_nonexistent_restaurant_returns_plain_404_json():
    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(uuid.uuid4()), "question": "hi"}
        )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["code"] == "restaurant_not_found"


async def test_chat_malformed_restaurant_id_returns_422():
    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": "not-a-uuid", "question": "hi"}
        )

    assert response.status_code == 422


async def test_chat_agent_unavailable_before_first_chunk_returns_503_json(
    seeded_restaurants, monkeypatch
):
    restaurant_id = next(iter(seeded_restaurants.values()))

    async def _failing_stream(restaurant_id, question):
        raise AgentUnavailableError("internal secret detail")
        yield  # pragma: no cover - makes this an async generator function

    monkeypatch.setattr("app.api.chat.answer_question_stream", _failing_stream)

    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
        )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"]["code"] == "agent_unavailable"
    assert "internal secret detail" not in response.text


async def test_chat_agent_incomplete_before_first_chunk_returns_502_json(
    seeded_restaurants, monkeypatch
):
    restaurant_id = next(iter(seeded_restaurants.values()))

    async def _failing_stream(restaurant_id, question):
        raise AgentIncompleteError("gave up")
        yield  # pragma: no cover - makes this an async generator function

    monkeypatch.setattr("app.api.chat.answer_question_stream", _failing_stream)

    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
        )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "agent_incomplete"


async def test_chat_agent_unavailable_mid_stream_sends_error_sse_event(
    seeded_restaurants, monkeypatch
):
    restaurant_id = next(iter(seeded_restaurants.values()))

    async def _mid_stream_failure(restaurant_id, question):
        yield TextChunk(text="Partial answer")
        raise AgentUnavailableError("internal secret detail")

    monkeypatch.setattr("app.api.chat.answer_question_stream", _mid_stream_failure)

    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    assert events[0] == {"type": "text_chunk", "text": "Partial answer"}
    assert events[1]["type"] == "error"
    assert events[1]["code"] == "agent_unavailable"
    assert "internal secret detail" not in response.text


async def test_chat_unexpected_exception_mid_stream_sends_generic_error_sse_event(
    seeded_restaurants, monkeypatch
):
    restaurant_id = next(iter(seeded_restaurants.values()))

    async def _mid_stream_bug(restaurant_id, question):
        yield TextChunk(text="Partial answer")
        raise RuntimeError("some internal invariant broke")

    monkeypatch.setattr("app.api.chat.answer_question_stream", _mid_stream_bug)

    async with await _client() as client:
        response = await client.post(
            "/chat", json={"restaurant_id": str(restaurant_id), "question": "hi"}
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    assert events[0] == {"type": "text_chunk", "text": "Partial answer"}
    assert events[1] == {
        "type": "error",
        "message": "An unexpected error occurred.",
        "code": "internal_error",
    }
    assert "some internal invariant broke" not in response.text
