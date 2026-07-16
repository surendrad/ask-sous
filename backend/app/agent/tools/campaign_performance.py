"""Campaign performance tool (Phase 8) — "how did this campaign do,"
comparing attributed transactions (transactions.campaign_id — synthetic in
seed data, see docs/decisions on campaign attribution) against the same
restaurant's baseline revenue in an equal-length window immediately before
the campaign was sent. `list_campaigns` lets the model (or a human via
chat) find the right campaign to ask about by name/date without already
knowing its UUID.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.agent.tools.db import readonly_connection

BASELINE_WINDOW_DAYS = 5

_LIST_CAMPAIGNS_SQL = text(
    "SELECT id, name, channel, sent_at FROM campaigns "
    "WHERE restaurant_id = :restaurant_id ORDER BY sent_at DESC"
)

_CAMPAIGN_SQL = text(
    "SELECT id, restaurant_id, name, sent_at FROM campaigns WHERE id = :campaign_id"
)

_ATTRIBUTED_SQL = text(
    "SELECT COUNT(*) AS transaction_count, COALESCE(SUM(total_amount), 0) AS revenue "
    "FROM transactions WHERE campaign_id = :campaign_id"
)

_BASELINE_SQL = text(
    "SELECT COUNT(*) AS transaction_count, COALESCE(SUM(total_amount), 0) AS revenue "
    "FROM transactions WHERE restaurant_id = :restaurant_id "
    "  AND transaction_time >= :baseline_start AND transaction_time < :baseline_end"
)


@dataclass(frozen=True)
class CampaignSummary:
    campaign_id: uuid.UUID
    name: str
    channel: str
    sent_at: datetime | None


@dataclass(frozen=True)
class CampaignPerformance:
    campaign_id: uuid.UUID
    campaign_name: str
    restaurant_id: uuid.UUID
    attributed_transaction_count: int
    attributed_revenue: Decimal
    baseline_transaction_count: int
    baseline_revenue: Decimal


async def list_campaigns(restaurant_id: uuid.UUID) -> list[CampaignSummary]:
    async with readonly_connection() as conn:
        result = await conn.execute(_LIST_CAMPAIGNS_SQL, {"restaurant_id": restaurant_id})
        return [
            CampaignSummary(
                campaign_id=row.id, name=row.name, channel=row.channel, sent_at=row.sent_at
            )
            for row in result.all()
        ]


def _build_campaign_performance(
    campaign_id: uuid.UUID,
    campaign_name: str,
    restaurant_id: uuid.UUID,
    attributed_transaction_count: int,
    attributed_revenue: Decimal,
    baseline_transaction_count: int,
    baseline_revenue: Decimal,
) -> CampaignPerformance:
    return CampaignPerformance(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        restaurant_id=restaurant_id,
        attributed_transaction_count=attributed_transaction_count,
        attributed_revenue=attributed_revenue,
        baseline_transaction_count=baseline_transaction_count,
        baseline_revenue=baseline_revenue,
    )


async def get_campaign_performance(campaign_id: uuid.UUID) -> CampaignPerformance:
    async with readonly_connection() as conn:
        campaign_result = await conn.execute(_CAMPAIGN_SQL, {"campaign_id": campaign_id})
        campaign_row = campaign_result.first()
        if campaign_row is None:
            raise ValueError(f"No campaign found for campaign_id {campaign_id!r}")

        attributed_result = await conn.execute(_ATTRIBUTED_SQL, {"campaign_id": campaign_id})
        attributed = attributed_result.one()

        baseline_transaction_count = 0
        baseline_revenue = Decimal("0")
        if campaign_row.sent_at is not None:
            baseline_start = campaign_row.sent_at - timedelta(days=BASELINE_WINDOW_DAYS)
            baseline_result = await conn.execute(
                _BASELINE_SQL,
                {
                    "restaurant_id": campaign_row.restaurant_id,
                    "baseline_start": baseline_start,
                    "baseline_end": campaign_row.sent_at,
                },
            )
            baseline_row = baseline_result.one()
            baseline_transaction_count = baseline_row.transaction_count
            baseline_revenue = baseline_row.revenue

    return _build_campaign_performance(
        campaign_id,
        campaign_row.name,
        campaign_row.restaurant_id,
        attributed.transaction_count,
        attributed.revenue,
        baseline_transaction_count,
        baseline_revenue,
    )
