"""Raw read-only SQL tool — lets the model answer questions the pre-built
aggregation tools can't. The single highest-risk piece of code in this
phase, because the query text itself originates, at least in part, from LLM
output. Three independent, redundant defence layers on top of the existing
DB-level read-only role (docs/decisions/002):

1. Structural SELECT-only validation via sqlglot (this module) — rejects
   write statements anywhere in the parsed tree, including inside CTEs.
2. A hard row cap applied via query wrapping (this module).
3. A statement timeout applied at execution time.

See docs/decisions/006-raw-sql-tool-safety-mechanism.md.
"""

from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlglot import exp

from app.agent.tools.db import readonly_connection

MAX_ROWS = 500
STATEMENT_TIMEOUT_MS = 5000

_WRITE_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Grant,
    exp.TruncateTable,
    exp.Command,
)


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


def _validate_select_only(query: str) -> None:
    statements = sqlglot.parse(query, dialect="postgres")
    if len(statements) != 1:
        raise ValueError("Only a single SQL statement is permitted.")

    statement = statements[0]
    if statement is None or not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT statements are permitted.")
    if statement.args.get("into") is not None:
        raise ValueError("SELECT ... INTO is not permitted.")

    write_node = next(statement.find_all(*_WRITE_NODE_TYPES), None)
    if write_node is not None:
        raise ValueError(f"Write operation ({type(write_node).__name__}) is not permitted.")


def _enforce_row_cap(query: str, max_rows: int = MAX_ROWS) -> str:
    return f"SELECT * FROM ({query}) AS _capped LIMIT {max_rows}"


async def run_readonly_query(
    query: str, params: dict[str, Any] | None = None, *, max_rows: int = MAX_ROWS
) -> QueryResult:
    _validate_select_only(query)
    capped_query = _enforce_row_cap(query, max_rows=max_rows)

    async with readonly_connection() as conn:
        await conn.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        result = await conn.execute(text(capped_query), params or {})
        rows = [dict(row._mapping) for row in result.all()]

    return QueryResult(
        rows=rows,
        row_count=len(rows),
        truncated=len(rows) == max_rows,
    )
