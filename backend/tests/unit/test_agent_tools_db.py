from unittest.mock import patch

from app.core.config import READONLY_DB_ROLE, Settings


def _fake_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://ask_sous:adminpass@localhost:5432/ask_sous",
        google_application_credentials="/tmp/key.json",
        gcp_project_id="test-project",
        gcp_region="us-central1",
        readonly_db_password="readonlypass",
    )


def test_readonly_database_url_uses_readonly_role_and_password():
    from app.agent.tools.db import readonly_database_url

    with patch("app.agent.tools.db.get_settings", return_value=_fake_settings()):
        url = readonly_database_url()

    assert f"{READONLY_DB_ROLE}:readonlypass@" in url
    assert "localhost:5432/ask_sous" in url


def test_readonly_database_url_differs_from_admin_url():
    from app.agent.tools.db import readonly_database_url

    settings = _fake_settings()
    with patch("app.agent.tools.db.get_settings", return_value=settings):
        readonly_url = readonly_database_url()

    assert readonly_url != settings.database_url
    assert "ask_sous:adminpass" not in readonly_url
