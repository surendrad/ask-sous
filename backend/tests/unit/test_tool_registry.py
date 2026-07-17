import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.agent.tool_registry import INSIGHTS_TOOLS, TOOL_DISPATCH, _to_jsonable
from app.agent.tools.cohort_comparison import _METRIC_EXPRESSIONS

_TOOL_NAMES = {
    "get_revenue_summary",
    "compare_periods",
    "get_item_velocity",
    "get_cohort_comparison",
    "run_readonly_query",
    "search_customer_reviews",
    "compare_locations",
    "list_campaigns",
    "get_campaign_performance",
    "get_upsell_metrics",
    "get_weekday_performance",
}

# Tools scoped to a single restaurant via `restaurant_id`, vs. a list via
# `restaurant_ids` (compare_locations/get_upsell_metrics), vs. neither
# (run_readonly_query has no restaurant scoping at all;
# get_campaign_performance is scoped by campaign_id instead).
_SINGLE_RESTAURANT_ID_TOOLS = {
    "get_revenue_summary",
    "compare_periods",
    "get_item_velocity",
    "get_cohort_comparison",
    "search_customer_reviews",
    "list_campaigns",
    "get_weekday_performance",
}
_MULTI_RESTAURANT_ID_TOOLS = {"compare_locations", "get_upsell_metrics"}


def test_insights_tools_has_expected_names():
    names = {decl.name for decl in INSIGHTS_TOOLS}
    assert names == _TOOL_NAMES


def test_single_restaurant_tools_have_restaurant_id_string_param():
    for decl in INSIGHTS_TOOLS:
        if decl.name not in _SINGLE_RESTAURANT_ID_TOOLS:
            continue
        assert "restaurant_id" in decl.parameters["properties"]
        assert decl.parameters["properties"]["restaurant_id"]["type"] == "STRING"


def test_multi_restaurant_tools_have_restaurant_ids_array_param():
    for decl in INSIGHTS_TOOLS:
        if decl.name not in _MULTI_RESTAURANT_ID_TOOLS:
            continue
        assert "restaurant_ids" in decl.parameters["properties"]
        assert decl.parameters["properties"]["restaurant_ids"]["type"] == "ARRAY"


def test_get_campaign_performance_has_campaign_id_param():
    decl = next(d for d in INSIGHTS_TOOLS if d.name == "get_campaign_performance")
    assert "campaign_id" in decl.parameters["properties"]
    assert decl.parameters["properties"]["campaign_id"]["type"] == "STRING"


def test_search_customer_reviews_has_query_and_top_k():
    decl = next(d for d in INSIGHTS_TOOLS if d.name == "search_customer_reviews")
    assert "restaurant_id" in decl.parameters["properties"]
    assert "query" in decl.parameters["properties"]
    assert "top_k" in decl.parameters["properties"]


def test_cohort_comparison_metric_enum_matches_allowlist():
    decl = next(d for d in INSIGHTS_TOOLS if d.name == "get_cohort_comparison")
    assert set(decl.parameters["properties"]["metric"]["enum"]) == set(_METRIC_EXPRESSIONS.keys())


def test_run_readonly_query_has_query_and_params():
    decl = next(d for d in INSIGHTS_TOOLS if d.name == "run_readonly_query")
    assert "query" in decl.parameters["properties"]
    assert "params" in decl.parameters["properties"]


def test_tool_dispatch_has_entry_per_declared_tool():
    assert set(TOOL_DISPATCH.keys()) == _TOOL_NAMES


@dataclass(frozen=True)
class _Nested:
    day: date
    amount: Decimal


@dataclass(frozen=True)
class _Fixture:
    restaurant_id: uuid.UUID
    total: Decimal
    breakdown: list[_Nested]


def test_to_jsonable_converts_decimal_date_uuid_and_nested_dataclasses():
    fixture = _Fixture(
        restaurant_id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        total=Decimal("1354.19"),
        breakdown=[_Nested(day=date(2026, 1, 1), amount=Decimal("10.50"))],
    )

    result = _to_jsonable(fixture)

    assert result == {
        "restaurant_id": "12345678-1234-5678-1234-567812345678",
        "total": "1354.19",
        "breakdown": [{"day": "2026-01-01", "amount": "10.50"}],
    }
    assert isinstance(result["total"], str)


def test_to_jsonable_decimal_preserves_exact_string_no_float_rounding():
    assert _to_jsonable(Decimal("1354.19")) == "1354.19"
