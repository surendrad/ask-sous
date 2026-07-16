import pytest
from pydantic import ValidationError

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/ask_sous",
    "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/key.json",
    "GCP_PROJECT_ID": "test-project",
    "GCP_REGION": "us-central1",
    "READONLY_DB_PASSWORD": "readonly-pass",
}


def _clear_env(monkeypatch):
    for key in [*REQUIRED_ENV.keys(), "ENABLE_TRICKLE"]:
        monkeypatch.delenv(key, raising=False)


def test_settings_raises_when_database_url_missing(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        if key != "DATABASE_URL":
            monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_raises_when_gcp_var_missing(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        if key != "GCP_PROJECT_ID":
            monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_with_all_required_vars(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.gcp_project_id == REQUIRED_ENV["GCP_PROJECT_ID"]


def test_enable_trickle_defaults_to_false(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.enable_trickle is False


def test_settings_raises_when_readonly_db_password_missing(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        if key != "READONLY_DB_PASSWORD":
            monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_loads_readonly_db_password(monkeypatch):
    from app.core.config import Settings

    _clear_env(monkeypatch)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.readonly_db_password == REQUIRED_ENV["READONLY_DB_PASSWORD"]


def test_constructing_settings_exports_google_application_credentials_to_os_environ(monkeypatch):
    import os

    from app.core.config import Settings

    _clear_env(monkeypatch)
    # Deliberately construct Settings entirely from constructor kwargs, not
    # env vars/`.env` — this proves the export happens as a side effect of
    # building a Settings instance, not because the value merely happened
    # to already be in os.environ beforehand (monkeypatch.setenv would have
    # put it there directly, which wouldn't actually test our code's
    # behavior).
    Settings(_env_file=None, **{k.lower(): v for k, v in REQUIRED_ENV.items()})

    # google.auth.default() (used by both GeminiClient and EmbeddingClient
    # under the hood) reads this OS environment variable directly — it has
    # no knowledge of our own pydantic Settings object, so the value must
    # actually be exported, not just parsed into Settings.
    assert (
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        == REQUIRED_ENV["GOOGLE_APPLICATION_CREDENTIALS"]
    )
