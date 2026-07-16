from datetime import timedelta

from app.agent.tools.upsell_metrics import get_upsell_metrics
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_get_upsell_metrics_returns_measurable_attach_rate(seeded_restaurants):
    rid = seeded_restaurants["Golden Skillet"]

    results = await get_upsell_metrics([rid], SEED_START_DATE, SEED_END_DATE)

    assert len(results) == 1
    metrics = results[0]
    assert metrics.total_transaction_count > 0
    assert metrics.transactions_with_upsell > 0
    assert metrics.upsell_revenue > 0
    # Target attach probability is 0.25 (UPSELL_ATTACH_PROBABILITY) — allow
    # real sampling variance over the full 90-day seed window.
    assert 0.15 <= metrics.attach_rate <= 0.35


async def test_get_upsell_metrics_multiple_locations_in_order(seeded_restaurants):
    ids = [seeded_restaurants["Golden Skillet"], seeded_restaurants["Bella Notte"]]

    results = await get_upsell_metrics(ids, SEED_START_DATE, SEED_END_DATE)

    assert len(results) == 2
    assert [r.restaurant_id for r in results] == ids
