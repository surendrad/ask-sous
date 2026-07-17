"""Explicit, hand-written function-calling schemas for the insights tools:
four Phase 2 aggregation tools, the raw SQL tool, search_customer_reviews
(Phase 4), four Phase 8 tools (compare_locations, list_campaigns,
get_campaign_performance, get_upsell_metrics), and get_weekday_performance
(shared by both insights Q&A and agentic campaign generation — see
docs/decisions/016-agentic-campaign-generation.md). Schemas are hand-written
rather than introspected from Python type hints because UUID/date/Decimal
don't map cleanly to JSON Schema.

TOOL_DISPATCH pairs each schema with:
- parse_args: JSON (str-keyed dict from the model) -> real Python kwargs
- func: the actual async tool function to call with those kwargs

_to_jsonable() is the single serializer used both to build the result fed
back to the model and to build the result logged for the audit trail
(app/agent/insights.py) — so what's logged and what the model saw are
provably the same object.
"""

import dataclasses
import datetime
import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any, NamedTuple

from app.agent.llm_client import ToolDeclaration
from app.agent.tools.campaign_performance import get_campaign_performance, list_campaigns
from app.agent.tools.cohort_comparison import _METRIC_EXPRESSIONS, get_cohort_comparison
from app.agent.tools.item_velocity import get_item_velocity
from app.agent.tools.locations_comparison import compare_locations
from app.agent.tools.period_comparison import compare_periods
from app.agent.tools.raw_sql import run_readonly_query
from app.agent.tools.revenue_summary import get_revenue_summary
from app.agent.tools.upsell_metrics import get_upsell_metrics
from app.agent.tools.vector_search import search_reviews
from app.agent.tools.weekday_performance import get_weekday_performance


def _to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _parse_uuid(raw: str, *, field_name: str = "restaurant_id") -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"Invalid {field_name} {raw!r}: {exc}") from exc


def _parse_date(raw: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid date {raw!r}: {exc}") from exc


class ToolSpec(NamedTuple):
    func: Callable[..., Any]
    parse_args: Callable[[dict[str, Any]], dict[str, Any]]


def _parse_restaurant_and_date_range(
    args: dict[str, Any], *, start_key: str, end_key: str
) -> dict[str, Any]:
    return {
        "restaurant_id": _parse_uuid(args["restaurant_id"]),
        start_key: _parse_date(args[start_key]),
        end_key: _parse_date(args[end_key]),
    }


def _parse_revenue_summary_args(args: dict[str, Any]) -> dict[str, Any]:
    return _parse_restaurant_and_date_range(args, start_key="start_date", end_key="end_date")


def _parse_weekday_performance_args(args: dict[str, Any]) -> dict[str, Any]:
    return _parse_restaurant_and_date_range(args, start_key="start_date", end_key="end_date")


def _parse_compare_periods_args(args: dict[str, Any]) -> dict[str, Any]:
    return _parse_restaurant_and_date_range(args, start_key="period_start", end_key="period_end")


def _parse_item_velocity_args(args: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_restaurant_and_date_range(args, start_key="window_start", end_key="window_end")
    if args.get("menu_item_name") is not None:
        parsed["menu_item_name"] = args["menu_item_name"]
    if args.get("top_n") is not None:
        parsed["top_n"] = int(args["top_n"])
    return parsed


def _parse_cohort_comparison_args(args: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_restaurant_and_date_range(args, start_key="start_date", end_key="end_date")
    if args.get("metric") is not None:
        parsed["metric"] = args["metric"]
    return parsed


def _parse_raw_sql_args(args: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {"query": args["query"]}
    if args.get("params") is not None:
        parsed["params"] = dict(args["params"])
    return parsed


def _parse_search_customer_reviews_args(args: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "restaurant_id": _parse_uuid(args["restaurant_id"]),
        "query": args["query"],
    }
    if args.get("top_k") is not None:
        parsed["top_k"] = int(args["top_k"])
    return parsed


def _parse_restaurant_ids_and_date_range(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "restaurant_ids": [
            _parse_uuid(r, field_name="restaurant_ids[]") for r in args["restaurant_ids"]
        ],
        "start_date": _parse_date(args["start_date"]),
        "end_date": _parse_date(args["end_date"]),
    }


def _parse_list_campaigns_args(args: dict[str, Any]) -> dict[str, Any]:
    return {"restaurant_id": _parse_uuid(args["restaurant_id"])}


def _parse_get_campaign_performance_args(args: dict[str, Any]) -> dict[str, Any]:
    return {"campaign_id": _parse_uuid(args["campaign_id"], field_name="campaign_id")}


_RESTAURANT_ID_PARAM = {"type": "STRING", "description": "The restaurant's UUID, as a string."}
_RESTAURANT_IDS_PARAM = {
    "type": "ARRAY",
    "items": {"type": "STRING"},
    "description": "The UUIDs of the selected restaurants, as strings.",
}
_DATE_PARAM_DESC = "An ISO-8601 date, e.g. 2026-06-15."


INSIGHTS_TOOLS: list[ToolDeclaration] = [
    ToolDeclaration(
        name="get_revenue_summary",
        description=(
            "Total revenue, transaction count, and daily breakdown for a "
            "restaurant over a date range."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "start_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "end_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
            },
            "required": ["restaurant_id", "start_date", "end_date"],
        },
    ),
    ToolDeclaration(
        name="compare_periods",
        description=(
            "Compares a period's revenue against the immediately prior period of the same length."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "period_start": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "period_end": {"type": "STRING", "description": _DATE_PARAM_DESC},
            },
            "required": ["restaurant_id", "period_start", "period_end"],
        },
    ),
    ToolDeclaration(
        name="get_item_velocity",
        description=(
            "Whether menu items are trending up or down in quantity sold, "
            "comparing the first and second half of a date window."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "window_start": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "window_end": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "menu_item_name": {
                    "type": "STRING",
                    "description": "Optional: filter to a single menu item by exact name.",
                },
                "top_n": {
                    "type": "INTEGER",
                    "description": "Optional: limit to the top N items by trend strength.",
                },
            },
            "required": ["restaurant_id", "window_start", "window_end"],
        },
    ),
    ToolDeclaration(
        name="get_cohort_comparison",
        description=(
            "Compares a restaurant's metric against the average of all other "
            "restaurants (its peers) over a date range."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "start_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "end_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "metric": {
                    "type": "STRING",
                    "enum": list(_METRIC_EXPRESSIONS.keys()),
                    "description": "Which metric to compare.",
                },
            },
            "required": ["restaurant_id", "start_date", "end_date"],
        },
    ),
    ToolDeclaration(
        name="run_readonly_query",
        description=(
            "Runs a read-only SQL SELECT query against the database, for questions the "
            "other tools can't answer. Only SELECT statements are permitted; the query is "
            "structurally validated and row-capped."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "A single SELECT statement. Use :name-style bind "
                        "parameters, never string-interpolated values."
                    ),
                },
                "params": {
                    "type": "OBJECT",
                    "description": "Optional bind parameter values, keyed by name.",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDeclaration(
        name="search_customer_reviews",
        description=(
            "Finds customer reviews for a restaurant that are semantically similar to a "
            "query, for qualitative questions like 'what are customers saying about X?' "
            "that a numeric aggregation tool can't answer."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "query": {
                    "type": "STRING",
                    "description": "What to search for, in natural language, e.g. 'wait times'.",
                },
                "top_k": {
                    "type": "INTEGER",
                    "description": "Optional: how many reviews to return (default 5, max 20).",
                },
            },
            "required": ["restaurant_id", "query"],
        },
    ),
    ToolDeclaration(
        name="compare_locations",
        description=(
            "Compares revenue, transaction count, and average ticket across two or more "
            "restaurants over the same date range — use this whenever more than one "
            "restaurant is in scope for the question, instead of calling the "
            "single-restaurant tools once per restaurant."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_ids": _RESTAURANT_IDS_PARAM,
                "start_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "end_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
            },
            "required": ["restaurant_ids", "start_date", "end_date"],
        },
    ),
    ToolDeclaration(
        name="list_campaigns",
        description=(
            "Lists a restaurant's past marketing campaigns (name, channel, send date) — "
            "use this first to find a campaign's id before calling get_campaign_performance, "
            "unless the caller already has the exact campaign_id."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {"restaurant_id": _RESTAURANT_ID_PARAM},
            "required": ["restaurant_id"],
        },
    ),
    ToolDeclaration(
        name="get_campaign_performance",
        description=(
            "How a specific past campaign performed: revenue and transaction count "
            "attributed to it, compared against that restaurant's own baseline revenue "
            "in the days immediately before the campaign was sent. Requires a campaign_id "
            "— use list_campaigns first if you only know the campaign by name or date."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "campaign_id": {
                    "type": "STRING",
                    "description": "The campaign's UUID, as a string.",
                }
            },
            "required": ["campaign_id"],
        },
    ),
    ToolDeclaration(
        name="get_weekday_performance",
        description=(
            "Revenue, transaction count, and average ticket grouped by day of the week "
            "(Monday through Sunday) for a restaurant over a date range — use this for "
            "any question about which weekday is busiest/slowest, instead of requesting "
            "get_revenue_summary's daily breakdown and grouping the days by weekday "
            "yourself. Always returns all seven weekdays, including ones with no activity."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_id": _RESTAURANT_ID_PARAM,
                "start_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "end_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
            },
            "required": ["restaurant_id", "start_date", "end_date"],
        },
    ),
    ToolDeclaration(
        name="get_upsell_metrics",
        description=(
            "Upsell attach rate (percentage of transactions that included a designated "
            "add-on item) and total upsell revenue, for one or more restaurants over a "
            "date range."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "restaurant_ids": _RESTAURANT_IDS_PARAM,
                "start_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
                "end_date": {"type": "STRING", "description": _DATE_PARAM_DESC},
            },
            "required": ["restaurant_ids", "start_date", "end_date"],
        },
    ),
]


TOOL_DISPATCH: dict[str, ToolSpec] = {
    "get_revenue_summary": ToolSpec(get_revenue_summary, _parse_revenue_summary_args),
    "compare_periods": ToolSpec(compare_periods, _parse_compare_periods_args),
    "get_item_velocity": ToolSpec(get_item_velocity, _parse_item_velocity_args),
    "get_cohort_comparison": ToolSpec(get_cohort_comparison, _parse_cohort_comparison_args),
    "run_readonly_query": ToolSpec(run_readonly_query, _parse_raw_sql_args),
    "search_customer_reviews": ToolSpec(search_reviews, _parse_search_customer_reviews_args),
    "compare_locations": ToolSpec(compare_locations, _parse_restaurant_ids_and_date_range),
    "list_campaigns": ToolSpec(list_campaigns, _parse_list_campaigns_args),
    "get_campaign_performance": ToolSpec(
        get_campaign_performance, _parse_get_campaign_performance_args
    ),
    "get_upsell_metrics": ToolSpec(get_upsell_metrics, _parse_restaurant_ids_and_date_range),
    "get_weekday_performance": ToolSpec(get_weekday_performance, _parse_weekday_performance_args),
}
