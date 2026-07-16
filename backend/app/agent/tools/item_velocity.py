"""Item velocity tool — "is this item trending up or down," by splitting a
window into a first half and second half and comparing quantity sold
between them.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

TREND_THRESHOLD_PCT = Decimal("15")

_ITEM_QUANTITY_BY_DAY_SQL = text(
    "SELECT t.transaction_time::date AS day, m.id AS menu_item_id, m.name AS menu_item_name, "
    "       m.category AS category, SUM(ti.quantity) AS quantity "
    "FROM transaction_items ti "
    "JOIN transactions t ON t.id = ti.transaction_id "
    "JOIN menu_items m ON m.id = ti.menu_item_id "
    "WHERE t.restaurant_id = :restaurant_id "
    "  AND t.transaction_time::date BETWEEN :window_start AND :window_end "
    "  AND (CAST(:menu_item_name AS text) IS NULL OR m.name = CAST(:menu_item_name AS text)) "
    "GROUP BY t.transaction_time::date, m.id, m.name, m.category"
)


@dataclass(frozen=True)
class ItemVelocity:
    menu_item_id: uuid.UUID
    menu_item_name: str
    category: str
    window_start: date
    window_end: date
    first_half_quantity: int
    second_half_quantity: int
    total_quantity: int
    quantity_change_pct: Decimal | None
    trend: str


def _window_midpoint(window_start: date, window_end: date) -> date:
    return window_start + (window_end - window_start) // 2 + timedelta(days=1)


def _build_item_velocities(
    window_start: date,
    window_end: date,
    rows: Sequence[tuple],
    *,
    top_n: int | None,
) -> list[ItemVelocity]:
    midpoint = _window_midpoint(window_start, window_end)

    by_item: dict[uuid.UUID, dict] = {}
    for day, menu_item_id, menu_item_name, category, quantity in rows:
        entry = by_item.setdefault(
            menu_item_id,
            {
                "menu_item_name": menu_item_name,
                "category": category,
                "first_half": 0,
                "second_half": 0,
            },
        )
        if day < midpoint:
            entry["first_half"] += quantity
        else:
            entry["second_half"] += quantity

    velocities = []
    for menu_item_id, entry in by_item.items():
        first_half = entry["first_half"]
        second_half = entry["second_half"]
        if first_half == 0 and second_half == 0:
            continue

        if first_half == 0:
            quantity_change_pct = None
            trend = "up"
        elif second_half == 0:
            quantity_change_pct = None
            trend = "down"
        else:
            quantity_change_pct = (Decimal(second_half - first_half) / first_half) * 100
            if quantity_change_pct > TREND_THRESHOLD_PCT:
                trend = "up"
            elif quantity_change_pct < -TREND_THRESHOLD_PCT:
                trend = "down"
            else:
                trend = "flat"

        velocities.append(
            ItemVelocity(
                menu_item_id=menu_item_id,
                menu_item_name=entry["menu_item_name"],
                category=entry["category"],
                window_start=window_start,
                window_end=window_end,
                first_half_quantity=first_half,
                second_half_quantity=second_half,
                total_quantity=first_half + second_half,
                quantity_change_pct=quantity_change_pct,
                trend=trend,
            )
        )

    # Python can't compare None ("infinite" change) to a Decimal directly, so
    # order explicitly: undefined-up first (strongest possible signal),
    # then finite changes descending, then undefined-down last.
    undefined_up = [v for v in velocities if v.quantity_change_pct is None and v.trend == "up"]
    defined_desc = sorted(
        (v for v in velocities if v.quantity_change_pct is not None),
        key=lambda v: v.quantity_change_pct,
        reverse=True,
    )
    undefined_down = [v for v in velocities if v.quantity_change_pct is None and v.trend == "down"]
    ordered = undefined_up + defined_desc + undefined_down

    return ordered[:top_n] if top_n is not None else ordered


async def get_item_velocity(
    restaurant_id: uuid.UUID,
    window_start: date,
    window_end: date,
    *,
    menu_item_name: str | None = None,
    top_n: int | None = None,
) -> list[ItemVelocity]:
    async with readonly_connection() as conn:
        result = await conn.execute(
            _ITEM_QUANTITY_BY_DAY_SQL,
            {
                "restaurant_id": restaurant_id,
                "window_start": window_start,
                "window_end": window_end,
                "menu_item_name": menu_item_name,
            },
        )
        rows = [
            (row.day, row.menu_item_id, row.menu_item_name, row.category, row.quantity)
            for row in result.all()
        ]
    return _build_item_velocities(window_start, window_end, rows, top_n=top_n)
