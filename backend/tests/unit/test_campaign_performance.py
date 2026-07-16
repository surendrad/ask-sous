import uuid
from decimal import Decimal

from app.agent.tools.campaign_performance import _build_campaign_performance


def test_build_campaign_performance_assembles_attributed_and_baseline_figures():
    campaign_id = uuid.uuid4()
    restaurant_id = uuid.uuid4()

    performance = _build_campaign_performance(
        campaign_id,
        "Taco Tuesday Blast",
        restaurant_id,
        18,
        Decimal("540.00"),
        12,
        Decimal("300.00"),
    )

    assert performance.campaign_id == campaign_id
    assert performance.campaign_name == "Taco Tuesday Blast"
    assert performance.restaurant_id == restaurant_id
    assert performance.attributed_transaction_count == 18
    assert performance.attributed_revenue == Decimal("540.00")
    assert performance.baseline_transaction_count == 12
    assert performance.baseline_revenue == Decimal("300.00")


def test_build_campaign_performance_zero_baseline_when_campaign_never_sent():
    # get_campaign_performance() passes 0/0 for a campaign with no sent_at —
    # there's no "before it was sent" window to compare against.
    campaign_id = uuid.uuid4()
    restaurant_id = uuid.uuid4()

    performance = _build_campaign_performance(
        campaign_id, "Draft Campaign", restaurant_id, 0, Decimal("0"), 0, Decimal("0")
    )

    assert performance.baseline_transaction_count == 0
    assert performance.baseline_revenue == Decimal("0")
    assert performance.attributed_transaction_count == 0
