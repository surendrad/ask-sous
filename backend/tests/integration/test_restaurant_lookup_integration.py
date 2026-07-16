import uuid

import pytest

from app.agent.tools.restaurant_lookup import get_brand_voice_guide, get_restaurant_names


async def test_get_brand_voice_guide_returns_string_for_known_restaurant(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]

    guide = await get_brand_voice_guide(golden_skillet_id)

    assert isinstance(guide, str)
    assert len(guide) > 0


async def test_get_brand_voice_guide_raises_for_unknown_restaurant(seeded_restaurants):
    with pytest.raises(ValueError, match="No restaurant found"):
        await get_brand_voice_guide(uuid.uuid4())


async def test_get_restaurant_names_returns_names_for_requested_ids_only(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]
    bella_notte_id = seeded_restaurants["Bella Notte"]

    names = await get_restaurant_names([golden_skillet_id, bella_notte_id])

    assert names == {
        golden_skillet_id: "Golden Skillet",
        bella_notte_id: "Bella Notte",
    }
    assert seeded_restaurants["Sakura Table"] not in names


async def test_get_restaurant_names_omits_unknown_ids_rather_than_erroring(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]
    unknown_id = uuid.uuid4()

    names = await get_restaurant_names([golden_skillet_id, unknown_id])

    assert names == {golden_skillet_id: "Golden Skillet"}
