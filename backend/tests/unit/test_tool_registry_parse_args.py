import uuid
from datetime import date

import pytest

from app.agent.tool_registry import TOOL_DISPATCH

_RID = "12345678-1234-5678-1234-567812345678"


def test_get_revenue_summary_parse_args_valid():
    parsed = TOOL_DISPATCH["get_revenue_summary"].parse_args(
        {"restaurant_id": _RID, "start_date": "2026-01-01", "end_date": "2026-01-31"}
    )
    assert parsed == {
        "restaurant_id": uuid.UUID(_RID),
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
    }


def test_get_revenue_summary_parse_args_invalid_uuid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_revenue_summary"].parse_args(
            {"restaurant_id": "not-a-uuid", "start_date": "2026-01-01", "end_date": "2026-01-31"}
        )


def test_get_revenue_summary_parse_args_invalid_date_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_revenue_summary"].parse_args(
            {"restaurant_id": _RID, "start_date": "not-a-date", "end_date": "2026-01-31"}
        )


def test_compare_periods_parse_args_valid():
    parsed = TOOL_DISPATCH["compare_periods"].parse_args(
        {"restaurant_id": _RID, "period_start": "2026-01-01", "period_end": "2026-01-07"}
    )
    assert parsed["period_start"] == date(2026, 1, 1)


def test_compare_periods_parse_args_invalid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["compare_periods"].parse_args(
            {"restaurant_id": "bad", "period_start": "2026-01-01", "period_end": "2026-01-07"}
        )


def test_get_item_velocity_parse_args_valid_with_optionals():
    parsed = TOOL_DISPATCH["get_item_velocity"].parse_args(
        {
            "restaurant_id": _RID,
            "window_start": "2026-01-01",
            "window_end": "2026-01-31",
            "menu_item_name": "Truffle Fries",
            "top_n": "5",
        }
    )
    assert parsed["menu_item_name"] == "Truffle Fries"
    assert parsed["top_n"] == 5


def test_get_item_velocity_parse_args_invalid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_item_velocity"].parse_args(
            {"restaurant_id": _RID, "window_start": "bad-date", "window_end": "2026-01-31"}
        )


def test_get_cohort_comparison_parse_args_valid_with_metric():
    parsed = TOOL_DISPATCH["get_cohort_comparison"].parse_args(
        {
            "restaurant_id": _RID,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "metric": "total_revenue",
        }
    )
    assert parsed["metric"] == "total_revenue"


def test_get_cohort_comparison_parse_args_invalid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_cohort_comparison"].parse_args(
            {"restaurant_id": _RID, "start_date": "bad", "end_date": "2026-01-31"}
        )


def test_run_readonly_query_parse_args_valid():
    parsed = TOOL_DISPATCH["run_readonly_query"].parse_args(
        {"query": "SELECT 1", "params": {"x": 1}}
    )
    assert parsed == {"query": "SELECT 1", "params": {"x": 1}}


def test_run_readonly_query_parse_args_missing_query_raises():
    with pytest.raises(KeyError):
        TOOL_DISPATCH["run_readonly_query"].parse_args({})


def test_search_customer_reviews_parse_args_valid():
    parsed = TOOL_DISPATCH["search_customer_reviews"].parse_args(
        {"restaurant_id": _RID, "query": "service quality", "top_k": "3"}
    )
    assert parsed == {
        "restaurant_id": uuid.UUID(_RID),
        "query": "service quality",
        "top_k": 3,
    }


def test_search_customer_reviews_parse_args_invalid_restaurant_id_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["search_customer_reviews"].parse_args(
            {"restaurant_id": "not-a-uuid", "query": "service quality"}
        )


_RID2 = "87654321-4321-8765-4321-876543218765"
_CID = "11111111-2222-3333-4444-555555555555"


def test_compare_locations_parse_args_valid():
    parsed = TOOL_DISPATCH["compare_locations"].parse_args(
        {
            "restaurant_ids": [_RID, _RID2],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }
    )
    assert parsed == {
        "restaurant_ids": [uuid.UUID(_RID), uuid.UUID(_RID2)],
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
    }


def test_compare_locations_parse_args_invalid_id_in_list_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["compare_locations"].parse_args(
            {
                "restaurant_ids": [_RID, "not-a-uuid"],
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            }
        )


def test_list_campaigns_parse_args_valid():
    parsed = TOOL_DISPATCH["list_campaigns"].parse_args({"restaurant_id": _RID})
    assert parsed == {"restaurant_id": uuid.UUID(_RID)}


def test_get_campaign_performance_parse_args_valid():
    parsed = TOOL_DISPATCH["get_campaign_performance"].parse_args({"campaign_id": _CID})
    assert parsed == {"campaign_id": uuid.UUID(_CID)}


def test_get_campaign_performance_parse_args_invalid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_campaign_performance"].parse_args({"campaign_id": "not-a-uuid"})


def test_get_upsell_metrics_parse_args_valid():
    parsed = TOOL_DISPATCH["get_upsell_metrics"].parse_args(
        {
            "restaurant_ids": [_RID],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        }
    )
    assert parsed["restaurant_ids"] == [uuid.UUID(_RID)]


def test_get_weekday_performance_parse_args_valid():
    parsed = TOOL_DISPATCH["get_weekday_performance"].parse_args(
        {"restaurant_id": _RID, "start_date": "2026-01-01", "end_date": "2026-01-31"}
    )
    assert parsed == {
        "restaurant_id": uuid.UUID(_RID),
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
    }


def test_get_weekday_performance_parse_args_invalid_uuid_raises():
    with pytest.raises(ValueError):
        TOOL_DISPATCH["get_weekday_performance"].parse_args(
            {"restaurant_id": "not-a-uuid", "start_date": "2026-01-01", "end_date": "2026-01-31"}
        )
