from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import REPO_ROOT

# The dedicated read-only Postgres role name (see docs/decisions/002-readonly-postgres-role.md).
# Single source of truth — imported by the role-creation migration and by
# the integration test suite, rather than each hand-typing the literal.
READONLY_DB_ROLE = "ask_sous_readonly"


class Settings(BaseSettings):
    """App configuration, loaded from environment variables / `.env`.

    Constructing this raises `pydantic.ValidationError` immediately if a
    required variable is missing, so the app fails fast at startup rather
    than failing later when a missing value is first used.
    """

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str
    google_application_credentials: str
    gcp_project_id: str
    gcp_region: str
    enable_trickle: bool = False
    readonly_db_password: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
