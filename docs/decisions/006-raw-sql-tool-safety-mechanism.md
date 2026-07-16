# ADR-006: Raw SQL Tool Safety Mechanism

**Date:** 2026-07-16
**Status:** Accepted

## Context

Phase 3 adds `run_readonly_query()` (`app/agent/tools/raw_sql.py`), letting
the model answer questions the four pre-built aggregation tools can't, by
writing its own SQL `SELECT`. This is the single highest-risk piece of code
added this phase: unlike every other tool, the query text itself originates,
at least in part, from LLM output. Standard SQL-injection defences
(parameterisation) don't fully apply here, because the injection surface
isn't a parameter value — it's the query structure itself.

The project already has one defence layer: the dedicated `ask_sous_readonly`
Postgres role (ADR-002), which cannot execute write statements no matter
what SQL reaches it. The question this ADR answers is whether that alone is
sufficient, or whether a second, independent layer is warranted before a
model-authored query ever reaches Postgres.

## Decision

Three independent, redundant layers, all applied before a query touches the
database — none depends on the others, so losing any one still leaves two:

1. **Structural SELECT-only validation** (`_validate_select_only()`), via
   `sqlglot`. Parses the query, requires exactly one statement, requires the
   root node to be a `Select`, rejects a `SELECT ... INTO` clause, and walks
   the full parsed tree rejecting `Insert`/`Update`/`Delete`/`Drop`/`Alter`/
   `Create`/`Grant`/`TruncateTable` nodes anywhere — including inside a CTE
   (`WITH x AS (DELETE FROM ... RETURNING *) SELECT * FROM x` is rejected,
   not just a bare `DELETE`).
2. **A hard row cap**, via query wrapping (`_enforce_row_cap()`):
   `SELECT * FROM (<query>) AS _capped LIMIT :max_rows`, rather than
   rewriting the query's own AST if it already has a `LIMIT`. Default cap
   is `MAX_ROWS = 500` — larger than the illustrative `200` in the phase
   plan's sketch, chosen because this project's seed data (tens of
   thousands of transaction rows) can legitimately produce a few hundred
   rows for a reasonable ad-hoc question without being truncated
   pointlessly; still small enough that even a maximally broad query stays
   cheap to serialize and log.
3. **A statement timeout**, applied via `SET LOCAL statement_timeout` at
   execution time, using a hardcoded constant — never interpolated from
   caller input.

The DB-level read-only role remains the true last line of defence: even in
the (currently untested-for) worst case where a write statement somehow
parsed as if it weren't one, `ask_sous_readonly` would still reject the
write at the database level. This two-layer relationship — structural
validation to keep obviously-bad queries from even reaching Postgres, the DB
role as the backstop — is deliberate; neither layer alone is treated as
sufficient on its own.

## Consequences

- The model gets a real escape hatch for ad-hoc questions (e.g. "what
  payment type is most common at Sakura Table?") without every possible
  question needing a bespoke aggregation tool.
- `sqlglot`'s validation is a static-analysis defence, not a formal proof.
  SQL is a large surface area; a sufficiently obscure Postgres-specific
  construct could theoretically slip past a general-purpose parser's
  write-detection in a way this phase's test suite doesn't anticipate. The
  DB role is what makes this an acceptable risk rather than a blocking one.
- `QueryResult.truncated` is an approximation (`row_count == max_rows`), not
  an exact "more rows existed" signal — an extra `COUNT(*)` query would
  double query cost for every raw-SQL call, which isn't worth it at this
  project's scale.
- Restaurant-scoping is intentionally *not* hard-enforced inside the SQL
  itself — the raw SQL tool exists precisely to answer cross-restaurant
  questions the pre-built tools (some deliberately cross-restaurant, like
  `get_cohort_comparison`) can't. There are no user accounts to violate
  (master-plan.md §2), so this is a UI/product scoping concern, not a
  SQL-level access-control gap.

## Alternatives Considered

- **DB-level read-only role alone, no additional validation.** Rejected:
  the role prevents writes but doesn't prevent expensive/runaway queries
  (no row cap, no timeout) or structurally surprising queries the model
  might generate. A single layer with no redundancy also means one bug in
  role configuration (e.g. an accidental grant) has no independent backstop.
- **Regex-based query rejection** (blocklist keywords like `DROP`,
  `DELETE`). Rejected: trivially defeated by whitespace/comment tricks or
  keywords appearing in string literals/column names; provides no real
  structural guarantee compared to actually parsing the query.
- **Rewriting the query's own `LIMIT` via AST manipulation** instead of
  wrapping. Rejected: wrapping is simpler and correct-by-construction (the
  outer `LIMIT` always wins as the enforced cap, regardless of what the
  inner query does), whereas AST rewriting requires correctly locating and
  replacing a `LIMIT` clause that may or may not already exist, in every
  dialect-specific position it could appear.
