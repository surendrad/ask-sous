"""Peer/cohort comparison tool — "how does this restaurant compare to its
peers" on a chosen metric.

The aggregate SQL expression is selected from a small, hardcoded allow-list
dict keyed by a closed set of metric names — NEVER built from a raw string
via f-string/.format() on caller input. Phase 3's function-calling schema
will eventually hand this function a plain string parsed from the model's
tool-call arguments, and a `Literal[...]` type hint alone provides no
runtime protection against that — hence the explicit ValueError guard below,
checked before any database call.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

CohortMetric = Literal["average_ticket", "total_revenue", "transaction_count"]

# The ONLY place in app/agent/tools/ where a SQL fragment is chosen by
# argument value. Safe because this dict is fixed, reviewed, and hardcoded —
# never constructed from caller-supplied text. Do not "simplify" this into
# an f-string built from the `metric` parameter.
_METRIC_EXPRESSIONS: dict[str, str] = {
    "average_ticket": "AVG(total_amount)",
    "total_revenue": "SUM(total_amount)",
    "transaction_count": "COUNT(*)",
}

_RESTAURANT_NAME_SQL = text("SELECT name FROM restaurants WHERE id = :restaurant_id")
_PEER_COUNT_SQL = text("SELECT COUNT(*) FROM restaurants WHERE id != :restaurant_id")


@dataclass(frozen=True)
class CohortComparison:
    restaurant_id: uuid.UUID
    restaurant_name: str
    metric: str
    start_date: date
    end_date: date
    restaurant_value: Decimal
    peer_value: Decimal
    peer_restaurant_count: int
    ratio_to_peers: Decimal | None


def _ratio(restaurant_value: Decimal, peer_value: Decimal) -> Decimal | None:
    return restaurant_value / peer_value if peer_value > 0 else None


async def get_cohort_comparison(
    restaurant_id: uuid.UUID,
    start_date: date,
    end_date: date,
    metric: CohortMetric = "average_ticket",
) -> CohortComparison:
    if metric not in _METRIC_EXPRESSIONS:
        raise ValueError(
            f"Unknown cohort metric {metric!r}; must be one of {sorted(_METRIC_EXPRESSIONS)}"
        )
    expression = _METRIC_EXPRESSIONS[metric]

    metric_sql = text(
        f"SELECT (r.id = :restaurant_id) AS is_target, {expression} AS metric_value "
        "FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id "
        "WHERE t.transaction_time::date BETWEEN :start_date AND :end_date "
        "GROUP BY is_target"
    )

    async with readonly_connection() as conn:
        name_result = await conn.execute(_RESTAURANT_NAME_SQL, {"restaurant_id": restaurant_id})
        restaurant_name = name_result.scalar_one()

        peer_count_result = await conn.execute(_PEER_COUNT_SQL, {"restaurant_id": restaurant_id})
        peer_restaurant_count = peer_count_result.scalar_one()

        metric_result = await conn.execute(
            metric_sql,
            {"restaurant_id": restaurant_id, "start_date": start_date, "end_date": end_date},
        )
        by_group = {row.is_target: row.metric_value for row in metric_result.all()}

    restaurant_value = Decimal(by_group.get(True) or 0)
    peer_value = Decimal(by_group.get(False) or 0)

    return CohortComparison(
        restaurant_id=restaurant_id,
        restaurant_name=restaurant_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        restaurant_value=restaurant_value,
        peer_value=peer_value,
        peer_restaurant_count=peer_restaurant_count,
        ratio_to_peers=_ratio(restaurant_value, peer_value),
    )
