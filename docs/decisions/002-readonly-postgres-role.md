# ADR-002: Read-Only Postgres Role Creation Mechanism

**Date:** 2026-07-15
**Status:** Accepted

## Context

CLAUDE.md establishes a hard boundary: the agent's DB tools (Phase 2 onward) must connect via a dedicated read-only Postgres role, never the same credentials used by migrations or the seed script. This role has to exist before Phase 2 needs it, be provably unable to write, and be reproducible from a clean database with a single command, matching the rest of the schema's migration-based lifecycle.

## Decision

The read-only role (`ask_sous_readonly`) is created by an Alembic migration (`0002_create_readonly_role`), not a separate init script, with the following mechanism:

1. **Existence check via `pg_roles`.** Postgres has no `CREATE ROLE IF NOT EXISTS` syntax, so the migration first queries `pg_roles` for an existing row with `rolname = 'ask_sous_readonly'` and only issues `CREATE ROLE` if it doesn't already exist — making the migration safely re-runnable.

2. **Password sourced from `READONLY_DB_PASSWORD`**, read via `os.environ` inside the migration at runtime — never hardcoded into the migration file. The repo-root `.env` is loaded into the real process environment via `python-dotenv` in `env.py` (and in `tests/conftest.py` for the test suite), since `pydantic-settings` alone only populates a `Settings` object, not `os.environ` itself, and this migration needs the latter.

3. **The password is passed via `sa.bindparam(..., literal_execute=True)`, not a driver-level bind parameter.** This is the one place the original plan's assumption didn't hold up in practice, discovered while implementing this phase:
   - The plan's initial approach was `CREATE ROLE ... PASSWORD :pwd` with `:pwd` sent as a normal SQLAlchemy/asyncpg bind parameter. This fails outright — Postgres's grammar for `CREATE ROLE ... PASSWORD` takes a string literal (`Sconst`), not a parameter placeholder, so asyncpg's extended query protocol produces `syntax error at or near "$1"`.
   - The plan correctly flagged a *different*, related pitfall — embedding the parameter inside a `DO $$ ... $$` block, where bind-parameter substitution doesn't reach into the dollar-quoted string body — but that pitfall doesn't apply here since this migration never uses a `DO` block for role creation.
   - The actual fix: `sa.text("CREATE ROLE ask_sous_readonly WITH LOGIN PASSWORD :pwd ...").bindparams(sa.bindparam("pwd", value=password, literal_execute=True))`. `literal_execute=True` tells SQLAlchemy to render the value as a properly escaped SQL literal at *compile* time rather than sending it as a driver parameter — satisfying Postgres's grammar while still avoiding manual string interpolation (the escaping is handled by SQLAlchemy's literal processor, not hand-rolled quote-doubling).

4. **Grants, applied every run (idempotent by nature — `GRANT`/`ALTER DEFAULT PRIVILEGES` don't error on repetition):**
   - `GRANT CONNECT ON DATABASE <db_name> TO ask_sous_readonly`
   - `GRANT USAGE ON SCHEMA public TO ask_sous_readonly`
   - `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ask_sous_readonly` — this is what makes every table Phase 1 creates automatically `SELECT`-able by the readonly role with no further per-table grants. It only applies to objects subsequently created *by the same role that ran this statement* (the admin/migration role), which holds by construction since Phase 1's migrations run under the same `DATABASE_URL` credentials as this one.

5. **Downgrade** revokes the grants and `DROP ROLE ask_sous_readonly` — acceptable for a local-only demo with no production downgrade-safety requirement.

Proven correct by three integration tests (`backend/tests/integration/test_db_bootstrap.py`), not just asserted: the readonly role can `SELECT` from a table it didn't create, and is rejected with `InsufficientPrivilege`/`permission denied` on `CREATE TABLE`, `INSERT`, and `DROP` against that same table.

## Consequences

- Easier: the role's existence and grants are versioned and reproducible via the same `alembic upgrade head` command as every other schema change — no separate script to remember to run, no drift between environments.
- Easier: the read-only boundary is a tested, falsifiable claim (three passing integration tests) rather than a documented intention.
- Harder: the migration file is less "pure schema" than a typical Alembic revision — it does role/permission management, which is a slightly unusual thing to find in a migrations folder. Mitigated by this ADR and inline comments explaining why.

## Alternatives Considered

- **Separate shell/SQL init script run outside Alembic** (e.g. a `db/init/` script mounted into the Postgres container at first boot) — rejected. This would create a second, unversioned mechanism for schema-adjacent state, running outside `alembic upgrade head`, and wouldn't re-apply cleanly if the role were ever manually dropped without also resetting the container's init-script marker.
- **Embedding password via string interpolation directly into the SQL text** — rejected outright as unsafe, even though the role name and database name (fixed, non-user-controlled literals) are interpolated directly in this migration; the password is exactly the kind of value that must go through a safe quoting mechanism, hence `literal_execute=True` rather than an f-string.
