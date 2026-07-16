"""Upsell measurement tool (Phase 8) — attach rate and revenue from
designated add-on/upsell menu items (menu_items.is_upsell), across one or
more selected locations. Takes a list from the start, since "measure
upsells in the selected locations" was the literal request — a
single-location call is just a list of one.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

_TOTAL_TRANSACTIONS_SQL = text(
    "SELECT COUNT(*) FROM transactions "
    "WHERE restaurant_id = :restaurant_id "
    "  AND transaction_time::date BETWEEN :start_date AND :end_date"
)

_UPSELL_METRICS_SQL = text(
    "SELECT COUNT(DISTINCT t.id) AS transactions_with_upsell, "
    "       COALESCE(SUM(ti.quantity * ti.unit_price), 0) AS upsell_revenue "
    "FROM transactions t "
    "JOIN transaction_items ti ON ti.transaction_id = t.id "
    "JOIN menu_items m ON m.id = ti.menu_item_id AND m.is_upsell = TRUE "
    "WHERE t.restaurant_id = :restaurant_id "
    "  AND t.transaction_time::date BETWEEN :start_date AND :end_date"
)


@dataclass(frozen=True)
class UpsellMetrics:
    restaurant_id: uuid.UUID
    start_date: date
    end_date: date
    total_transaction_count: int
    transactions_with_upsell: int
    upsell_revenue: Decimal
    attach_rate: Decimal


def _build_upsell_metrics(
    restaurant_id: uuid.UUID,
    start_date: date,
    end_date: date,
    total_transaction_count: int,
    transactions_with_upsell: int,
    upsell_revenue: Decimal,
) -> UpsellMetrics:
    attach_rate = (
        Decimal(transactions_with_upsell) / Decimal(total_transaction_count)
        if total_transaction_count > 0
        else Decimal("0")
    )
    return UpsellMetrics(
        restaurant_id=restaurant_id,
        start_date=start_date,
        end_date=end_date,
        total_transaction_count=total_transaction_count,
        transactions_with_upsell=transactions_with_upsell,
        upsell_revenue=upsell_revenue,
        attach_rate=attach_rate,
    )


async def _get_one_location_upsell_metrics(
    restaurant_id: uuid.UUID, start_date: date, end_date: date
) -> UpsellMetrics:
    async with readonly_connection() as conn:
        total_result = await conn.execute(
            _TOTAL_TRANSACTIONS_SQL,
            {"restaurant_id": restaurant_id, "start_date": start_date, "end_date": end_date},
        )
        total_transaction_count = total_result.scalar_one()

        upsell_result = await conn.execute(
            _UPSELL_METRICS_SQL,
            {"restaurant_id": restaurant_id, "start_date": start_date, "end_date": end_date},
        )
        upsell_row = upsell_result.one()

    return _build_upsell_metrics(
        restaurant_id,
        start_date,
        end_date,
        total_transaction_count,
        upsell_row.transactions_with_upsell,
        upsell_row.upsell_revenue,
    )


async def get_upsell_metrics(
    restaurant_ids: list[uuid.UUID], start_date: date, end_date: date
) -> list[UpsellMetrics]:
    return list(
        await asyncio.gather(
            *(_get_one_location_upsell_metrics(rid, start_date, end_date) for rid in restaurant_ids)
        )
    )
