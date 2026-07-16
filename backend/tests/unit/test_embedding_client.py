from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors, types

from app.agent.embedding_client import EMBEDDING_DIMENSIONS, EmbeddingClient
from app.agent.exceptions import AgentUnavailableError
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


def _embedding_response(vectors: list[list[float]]) -> types.EmbedContentResponse:
    return types.EmbedContentResponse(
        embeddings=[types.ContentEmbedding(values=v) for v in vectors]
    )


def test_embedding_client_constructs_vertex_client_from_settings():
    settings = _settings(gcp_project_id="my-project", gcp_region="europe-west1")

    with patch("app.agent.embedding_client.genai.Client") as mock_client_cls:
        EmbeddingClient(settings=settings)

    mock_client_cls.assert_called_once_with(
        vertexai=True, project="my-project", location="europe-west1"
    )


async def test_embed_texts_translates_response_order_preserving():
    vec_a = [0.1] * EMBEDDING_DIMENSIONS
    vec_b = [0.2] * EMBEDDING_DIMENSIONS
    response = _embedding_response([vec_a, vec_b])

    client = EmbeddingClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.embed_content = MagicMock(return_value=response)

    result = await client.embed_texts(["a", "b"])

    assert result == [vec_a, vec_b]


async def test_embed_texts_translates_api_error_to_agent_unavailable():
    client = EmbeddingClient(settings=_settings())
    client._client = MagicMock()
    original = errors.APIError(code=503, response_json={"error": {"message": "unavailable"}})
    client._client.models.embed_content = MagicMock(side_effect=original)

    with pytest.raises(AgentUnavailableError) as exc_info:
        await client.embed_texts(["a"])

    assert exc_info.value.__cause__ is original


async def test_embed_texts_translates_missing_credentials_to_agent_unavailable():
    client = EmbeddingClient(settings=_settings())
    client._client = MagicMock()
    original = DefaultCredentialsError("no credentials found")
    client._client.models.embed_content = MagicMock(side_effect=original)

    with pytest.raises(AgentUnavailableError) as exc_info:
        await client.embed_texts(["a"])

    assert exc_info.value.__cause__ is original


async def test_embed_texts_rejects_wrong_dimension_vector():
    response = _embedding_response([[0.1, 0.2, 0.3]])

    client = EmbeddingClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.embed_content = MagicMock(return_value=response)

    with pytest.raises(ValueError, match="index 0"):
        await client.embed_texts(["a"])


async def test_embed_texts_is_deterministic_at_plumbing_level():
    vec = [0.5] * EMBEDDING_DIMENSIONS
    response = _embedding_response([vec])

    client = EmbeddingClient(settings=_settings())
    client._client = MagicMock()
    client._client.models.embed_content = MagicMock(return_value=response)

    first = await client.embed_texts(["same text"])
    second = await client.embed_texts(["same text"])

    assert first == second
