"""A second, narrowly-scoped Vertex AI adapter — alongside llm_client.py,
the only other module permitted to import google.genai. Mirrors
GeminiClient's pattern exactly: plain Python types in and out
(list[str] -> list[list[float]]), SDK objects constructed only inside this
module. See docs/decisions/008-embedding-model-and-client-adapter.md.
"""

import asyncio

import structlog
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import errors

from app.agent.exceptions import AgentUnavailableError
from app.core.config import Settings, get_settings

logger = structlog.get_logger()

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSIONS = 768


def _validate_dimensions(vectors: list[list[float]]) -> None:
    for index, vector in enumerate(vectors):
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Embedding at index {index} has {len(vector)} dimensions, "
                f"expected {EMBEDDING_DIMENSIONS}."
            )


class EmbeddingClient:
    """Thin adapter over google.genai.Client's embedding call."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._client = genai.Client(
            vertexai=True, project=settings.gcp_project_id, location=settings.gcp_region
        )

    async def embed_texts(
        self, texts: list[str], model: str = EMBEDDING_MODEL
    ) -> list[list[float]]:
        try:
            response = await asyncio.to_thread(
                self._client.models.embed_content, model=model, contents=texts
            )
        except (errors.APIError, errors.ClientError, errors.ServerError, GoogleAuthError) as exc:
            logger.error("embedding_call_failed", exc_info=exc)
            raise AgentUnavailableError(
                "The embedding service is temporarily unavailable."
            ) from exc

        vectors = [list(embedding.values) for embedding in response.embeddings]
        _validate_dimensions(vectors)
        return vectors
