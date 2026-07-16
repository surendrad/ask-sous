from datetime import timedelta

from app.agent.tools.locations_comparison import compare_locations
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_compare_locations_returns_one_summary_per_restaurant_in_order(seeded_restaurants):
    ids = [
        seeded_restaurants["Golden Skillet"],
        seeded_restaurants["Bella Notte"],
        seeded_restaurants["Sakura Table"],
    ]

    results = await compare_locations(ids, SEED_START_DATE, SEED_END_DATE)

    assert len(results) == 3
    assert [r.restaurant_id for r in results] == ids
    for r in results:
        assert r.total_revenue > 0
        assert r.transaction_count > 0


async def test_compare_locations_single_id_behaves_like_revenue_summary(seeded_restaurants):
    rid = seeded_restaurants["Golden Skillet"]

    results = await compare_locations([rid], SEED_START_DATE, SEED_END_DATE)

    assert len(results) == 1
    assert results[0].restaurant_id == rid
