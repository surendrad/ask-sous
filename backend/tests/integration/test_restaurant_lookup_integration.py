import uuid

import pytest

from app.agent.tools.restaurant_lookup import get_brand_voice_guide


async def test_get_brand_voice_guide_returns_string_for_known_restaurant(seeded_restaurants):
    golden_skillet_id = seeded_restaurants["Golden Skillet"]

    guide = await get_brand_voice_guide(golden_skillet_id)

    assert isinstance(guide, str)
    assert len(guide) > 0


async def test_get_brand_voice_guide_raises_for_unknown_restaurant(seeded_restaurants):
    with pytest.raises(ValueError, match="No restaurant found"):
        await get_brand_voice_guide(uuid.uuid4())
