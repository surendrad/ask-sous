from dotenv import load_dotenv

from app.core.paths import REPO_ROOT

# Load the repo-root `.env` into the real process environment (not just into
# a pydantic-settings object) so both `Settings` and any direct
# `os.environ[...]` reads (e.g. the readonly-role migration) see the same
# values during tests.
load_dotenv(REPO_ROOT / ".env")
