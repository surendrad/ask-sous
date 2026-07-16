import uuid
from datetime import date
from decimal import Decimal

from app.agent.tools.upsell_metrics import _build_upsell_metrics


def test_build_upsell_metrics_computes_attach_rate():
    rid = uuid.uuid4()
    metrics = _build_upsell_metrics(
        rid, date(2026, 1, 1), date(2026, 1, 7), 100, 25, Decimal("125.00")
    )

    assert metrics.attach_rate == Decimal("0.25")
    assert metrics.upsell_revenue == Decimal("125.00")
    assert metrics.total_transaction_count == 100
    assert metrics.transactions_with_upsell == 25


def test_build_upsell_metrics_zero_transactions_is_zero_not_error():
    rid = uuid.uuid4()
    metrics = _build_upsell_metrics(rid, date(2026, 1, 1), date(2026, 1, 7), 0, 0, Decimal("0"))

    assert metrics.attach_rate == Decimal("0")
