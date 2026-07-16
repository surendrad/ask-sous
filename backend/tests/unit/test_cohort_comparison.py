import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools.cohort_comparison import _ratio, get_cohort_comparison


def test_ratio_computes_division():
    assert _ratio(Decimal("100"), Decimal("50")) == Decimal("2")


def test_ratio_zero_peer_value_gives_none_not_zerodivisionerror():
    assert _ratio(Decimal("100"), Decimal("0")) is None


async def test_get_cohort_comparison_rejects_invalid_metric_before_any_db_call():
    fail_if_called = AsyncMock(side_effect=AssertionError("should not open a DB connection"))

    with patch("app.agent.tools.cohort_comparison.readonly_connection", fail_if_called):
        with pytest.raises(ValueError, match="not_a_real_metric"):
            await get_cohort_comparison(
                uuid.uuid4(), date(2026, 1, 1), date(2026, 1, 31), metric="not_a_real_metric"
            )

    fail_if_called.assert_not_called()
