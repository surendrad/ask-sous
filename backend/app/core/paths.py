from pathlib import Path

# Anchored off this file's own location, not the process cwd — reliable
# regardless of where a command is launched from. Single source of truth for
# "where is the repo root", used by Settings' env_file, the Alembic env.py,
# and the test suite's root conftest.py.
REPO_ROOT = Path(__file__).resolve().parents[3]
