from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors

from app.agent.exceptions import AgentIncompleteError, AgentUnavailableError
from app.agent.llm_client import GeminiClient, UserText
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://x:y@localhost/db",
        google_application_credentials="/path/to/key.json",
        gcp_project_id="ask-sous-dev",
        gcp_region="us-central1",
        readonly_db_password="pw",
    )


async def test_api_error_translated_to_agent_unavailable_with_cause_preserved():
    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    original = errors.APIError(code=503, response_json={"error": {"message": "rate limited"}})
    client._client.models.generate_content = MagicMock(side_effect=original)

    with pytest.raises(AgentUnavailableError) as exc_info:
        await client.generate_turn(history=[UserText("hi")], tools=[])

    assert exc_info.value.__cause__ is original


async def test_missing_credentials_error_translated_to_agent_unavailable():
    client = GeminiClient(settings=_settings())
    client._client = MagicMock()
    original = DefaultCredentialsError("no credentials found")
    client._client.models.generate_content = MagicMock(side_effect=original)

    with pytest.raises(AgentUnavailableError) as exc_info:
        await client.generate_turn(history=[UserText("hi")], tools=[])

    assert exc_info.value.__cause__ is original


def test_agent_incomplete_error_is_a_plain_exception():
    assert issubclass(AgentIncompleteError, Exception)
    assert issubclass(AgentUnavailableError, Exception)
