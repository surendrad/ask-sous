"""Restaurant-scoped lookups that don't fit the aggregation-tool or
raw-SQL-tool shape: the brand voice guide fetch campaign generation (Phase
5) needs, the existence check both /chat and /campaigns use, and the
restaurant list the frontend's restaurant switcher (Phase 6) needs.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

_BRAND_VOICE_GUIDE_SQL = text("SELECT brand_voice_guide FROM restaurants WHERE id = :restaurant_id")
_RESTAURANT_EXISTS_SQL = text("SELECT 1 FROM restaurants WHERE id = :restaurant_id")
_LIST_RESTAURANTS_SQL = text("SELECT id, name FROM restaurants ORDER BY name")
_RESTAURANT_NAMES_SQL = text("SELECT id, name FROM restaurants WHERE id = ANY(:restaurant_ids)")


@dataclass(frozen=True)
class RestaurantSummary:
    id: uuid.UUID
    name: str


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


async def list_restaurants() -> list[RestaurantSummary]:
    async with readonly_connection() as conn:
        result = await conn.execute(_LIST_RESTAURANTS_SQL)
        rows = result.all()
    return [RestaurantSummary(id=row.id, name=row.name) for row in rows]


async def get_restaurant_names(restaurant_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Name lookup for a specific set of restaurant_ids — used to give the
    model human-readable names to answer with (Phase 8: a live multi-location
    question surfaced the agent referring to restaurants by raw UUID in its
    answer, since nothing before this ever gave it a name). Unknown ids are
    silently omitted rather than raising, since callers only use this to
    enrich a prompt, not to validate existence."""
    async with readonly_connection() as conn:
        result = await conn.execute(_RESTAURANT_NAMES_SQL, {"restaurant_ids": restaurant_ids})
        rows = result.all()
    return {row.id: row.name for row in rows}
