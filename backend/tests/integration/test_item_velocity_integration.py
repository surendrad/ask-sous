from datetime import timedelta

from app.agent.tools.item_velocity import get_item_velocity
from app.seed.generators import SEED_END_DATE, SEED_WINDOW_DAYS

SEED_START_DATE = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)


async def test_get_item_velocity_no_matching_item_returns_empty_list(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]

    velocities = await get_item_velocity(
        golden_skillet_id,
        SEED_START_DATE,
        SEED_END_DATE,
        menu_item_name="Truffle Fries",  # only exists at Bella Notte
    )

    assert velocities == []


async def test_get_item_velocity_returns_data_for_real_restaurant(seeded_restaurants):
    bella_notte_id = seeded_restaurants["Bella Notte"]

    velocities = await get_item_velocity(bella_notte_id, SEED_START_DATE, SEED_END_DATE)

    assert len(velocities) > 0
    assert all(v.total_quantity > 0 for v in velocities)
