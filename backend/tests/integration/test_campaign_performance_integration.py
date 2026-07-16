import uuid

import pytest
from sqlalchemy import select

from app.agent.tools.campaign_performance import get_campaign_performance, list_campaigns
from app.db.models import Campaign


async def test_list_campaigns_returns_campaigns_for_restaurant(seeded_restaurants):
    rid = seeded_restaurants["Golden Skillet"]

    campaigns = await list_campaigns(rid)

    assert 3 <= len(campaigns) <= 5
    for c in campaigns:
        assert c.name
        assert c.channel in {"sms", "email", "social"}
        assert c.sent_at is not None


async def test_list_campaigns_sorted_by_sent_at_descending(seeded_restaurants):
    rid = seeded_restaurants["Golden Skillet"]

    campaigns = await list_campaigns(rid)

    sent_ats = [c.sent_at for c in campaigns]
    assert sent_ats == sorted(sent_ats, reverse=True)


async def test_get_campaign_performance_returns_attributed_and_baseline_data(
    admin_engine, seeded_restaurants
):
    rid = seeded_restaurants["Golden Skillet"]
    campaigns = await list_campaigns(rid)
    campaign_id = campaigns[0].campaign_id

    performance = await get_campaign_performance(campaign_id)

    assert performance.campaign_id == campaign_id
    assert performance.restaurant_id == rid
    assert performance.campaign_name
    assert performance.attributed_transaction_count >= 0
    assert performance.attributed_revenue >= 0
    assert performance.baseline_transaction_count >= 0
    assert performance.baseline_revenue >= 0


async def test_get_campaign_performance_unknown_campaign_raises(seeded_restaurants):
    with pytest.raises(ValueError, match="No campaign found"):
        await get_campaign_performance(uuid.uuid4())


async def test_get_campaign_performance_attributed_revenue_matches_real_attribution(
    admin_engine, seeded_restaurants
):
    # Cross-check the tool's own attributed_revenue against a direct query
    # of transactions.campaign_id — proves the tool is reading the real
    # attribution column, not some independently-computed approximation.
    from sqlalchemy import func
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import Transaction

    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    rid = seeded_restaurants["Golden Skillet"]

    async with session_maker() as session:
        result = await session.execute(select(Campaign.id).where(Campaign.restaurant_id == rid))
        campaign_ids = [row[0] for row in result.all()]

        attributed_campaign_id = None
        for cid in campaign_ids:
            count_result = await session.execute(
                select(func.count()).select_from(Transaction).where(Transaction.campaign_id == cid)
            )
            if count_result.scalar_one() > 0:
                attributed_campaign_id = cid
                break

        assert attributed_campaign_id is not None, "expected at least one attributed campaign"

        revenue_result = await session.execute(
            select(func.coalesce(func.sum(Transaction.total_amount), 0)).where(
                Transaction.campaign_id == attributed_campaign_id
            )
        )
        expected_revenue = revenue_result.scalar_one()

    performance = await get_campaign_performance(attributed_campaign_id)
    assert performance.attributed_revenue == expected_revenue
