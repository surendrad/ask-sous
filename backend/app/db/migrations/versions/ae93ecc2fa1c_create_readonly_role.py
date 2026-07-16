"""create_readonly_role

Creates the dedicated read-only Postgres role (`ask_sous_readonly`) that the
agent's DB tools will exclusively use from Phase 2 onward. See
docs/decisions/002-readonly-postgres-role.md for the full rationale.

Revision ID: ae93ecc2fa1c
Revises: 7057c2be6551
Create Date: 2026-07-15 13:07:38.986400

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import READONLY_DB_ROLE

# revision identifiers, used by Alembic.
revision: str = "ae93ecc2fa1c"
down_revision: str | Sequence[str] | None = "7057c2be6551"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READONLY_ROLE = READONLY_DB_ROLE


def upgrade() -> None:
    connection = op.get_bind()
    password = os.environ["READONLY_DB_PASSWORD"]
    db_name = connection.engine.url.database

    role_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
        {"role": READONLY_ROLE},
    ).scalar()

    if not role_exists:
        # Postgres has no `CREATE ROLE IF NOT EXISTS`, hence the existence
        # check above. `CREATE ROLE ... PASSWORD` takes a string literal in
        # Postgres's grammar, not a driver-level bind parameter — a plain
        # `:pwd` sent as an asyncpg parameter fails with a syntax error
        # ("near $1"), and embedding it inside a `DO $$ ... $$` block doesn't
        # help either, since substitution never reaches into the dollar-quoted
        # string body. `literal_execute=True` tells SQLAlchemy to render the
        # value as a properly escaped SQL literal at compile time instead of
        # sending it as a driver parameter — safe against injection (the
        # escaping is handled by SQLAlchemy's literal processor) while still
        # satisfying Postgres's grammar. See ADR-002.
        connection.execute(
            sa.text(
                f"CREATE ROLE {READONLY_ROLE} WITH LOGIN PASSWORD :pwd "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE"
            ).bindparams(sa.bindparam("pwd", value=password, literal_execute=True))
        )

    connection.execute(sa.text(f"GRANT CONNECT ON DATABASE {db_name} TO {READONLY_ROLE}"))
    connection.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {READONLY_ROLE}"))
    # Applies to tables created by the role running this migration (the
    # admin/migration role) from this point on — so every table Phase 1
    # creates is automatically SELECT-able with no further per-table grants.
    connection.execute(
        sa.text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {READONLY_ROLE}"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    db_name = connection.engine.url.database

    connection.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE SELECT ON TABLES FROM {READONLY_ROLE}"
        )
    )
    connection.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {READONLY_ROLE}"))
    connection.execute(sa.text(f"REVOKE CONNECT ON DATABASE {db_name} FROM {READONLY_ROLE}"))
    connection.execute(sa.text(f"DROP ROLE IF EXISTS {READONLY_ROLE}"))
