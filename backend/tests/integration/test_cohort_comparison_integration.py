from datetime import timedelta
from decimal import Decimal

from app.agent.tools.cohort_comparison import get_cohort_comparison
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_get_cohort_comparison_zero_transactions_everywhere(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]
    before_window = SEED_START_DATE - timedelta(days=60)

    result = await get_cohort_comparison(golden_skillet_id, before_window, before_window)

    assert result.restaurant_value == Decimal("0")
    assert result.peer_value == Decimal("0")
    assert result.ratio_to_peers is None


async def test_get_cohort_comparison_returns_restaurant_name_and_peer_count(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]

    result = await get_cohort_comparison(golden_skillet_id, SEED_START_DATE, SEED_END_DATE)

    assert result.restaurant_name == "Golden Skillet"
    assert result.peer_restaurant_count == 4
