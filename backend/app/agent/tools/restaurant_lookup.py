"""Restaurant-scoped lookups that don't fit the aggregation-tool or
raw-SQL-tool shape — currently just the brand voice guide fetch that
campaign generation (Phase 5) needs before it can call the model.
"""

import uuid

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

_BRAND_VOICE_GUIDE_SQL = text("SELECT brand_voice_guide FROM restaurants WHERE id = :restaurant_id")
_RESTAURANT_EXISTS_SQL = text("SELECT 1 FROM restaurants WHERE id = :restaurant_id")


async def get_brand_voice_guide(restaurant_id: uuid.UUID) -> str:
    async with readonly_connection() as conn:
        result = await conn.execute(_BRAND_VOICE_GUIDE_SQL, {"restaurant_id": restaurant_id})
        row = result.first()

    if row is None:
        raise ValueError(f"No restaurant found for restaurant_id {restaurant_id!r}")
    return row.brand_voice_guide


async def restaurant_exists(restaurant_id: uuid.UUID) -> bool:
    async with readonly_connection() as conn:
        result = await conn.execute(_RESTAURANT_EXISTS_SQL, {"restaurant_id": restaurant_id})
        return result.first() is not None
