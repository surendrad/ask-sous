import uuid
from unittest.mock import AsyncMock, patch

from app.agent.tools.vector_search import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    CampaignSearchResult,
    ReviewSearchResult,
    SimilarCampaign,
    SimilarReview,
    _clamp_top_k,
    _format_vector_literal,
    search_reviews,
    search_similar_campaigns,
)

_RID = uuid.uuid4()


def test_format_vector_literal_three_elements():
    assert _format_vector_literal([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"


def test_format_vector_literal_empty():
    assert _format_vector_literal([]) == "[]"


def test_format_vector_literal_no_escaping_needed_characters():
    literal = _format_vector_literal([1.5, -2.25, 0.0])
    assert all(c not in literal for c in ("'", '"', "\\"))


def test_clamp_top_k_none_returns_default():
    assert _clamp_top_k(None) == DEFAULT_TOP_K


def test_clamp_top_k_within_range_passes_through():
    assert _clamp_top_k(3) == 3


def test_clamp_top_k_above_max_clamps():
    assert _clamp_top_k(MAX_TOP_K + 50) == MAX_TOP_K


def test_clamp_top_k_zero_or_negative_clamps_to_one():
    assert _clamp_top_k(0) == 1
    assert _clamp_top_k(-5) == 1


async def test_search_reviews_embeds_query_and_maps_rows():
    fake_client = AsyncMock()
    fake_client.embed_texts = AsyncMock(return_value=[[0.1] * 768])

    fake_row = type(
        "Row",
        (),
        {"id": uuid.uuid4(), "review_text": "Great food", "rating": 5, "distance": 0.01},
    )()

    with (
        patch("app.agent.tools.vector_search.EmbeddingClient", return_value=fake_client),
        patch(
            "app.agent.tools.vector_search._fetch_review_matches",
            AsyncMock(return_value=[fake_row]),
        ),
    ):
        result = await search_reviews(_RID, "great food", top_k=3)

    fake_client.embed_texts.assert_awaited_once_with(["great food"])
    assert isinstance(result, ReviewSearchResult)
    assert result.matches == [
        SimilarReview(review_id=fake_row.id, review_text="Great food", rating=5, distance=0.01)
    ]


async def test_search_similar_campaigns_embeds_reference_and_maps_rows():
    fake_client = AsyncMock()
    fake_client.embed_texts = AsyncMock(return_value=[[0.2] * 768])

    fake_row = type(
        "Row", (), {"id": uuid.uuid4(), "copy_text": "50% off tacos", "distance": 0.05}
    )()

    with (
        patch("app.agent.tools.vector_search.EmbeddingClient", return_value=fake_client),
        patch(
            "app.agent.tools.vector_search._fetch_campaign_matches",
            AsyncMock(return_value=[fake_row]),
        ),
    ):
        result = await search_similar_campaigns(_RID, "taco promotion", top_k=2)

    fake_client.embed_texts.assert_awaited_once_with(["taco promotion"])
    assert isinstance(result, CampaignSearchResult)
    assert result.matches == [
        SimilarCampaign(campaign_id=fake_row.id, copy_text="50% off tacos", distance=0.05)
    ]
