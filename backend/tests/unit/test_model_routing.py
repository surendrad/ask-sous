from app.agent.insights import ESCALATION_TOOL_CALL_THRESHOLD, _select_model
from app.agent.llm_client import FLASH_MODEL, PRO_MODEL


def test_default_selects_flash():
    assert _select_model("what was my revenue last week?", completed_tool_call_rounds=0) == (
        FLASH_MODEL,
        "default",
    )


def test_tool_call_threshold_escalates_to_pro():
    assert _select_model(
        "keep digging", completed_tool_call_rounds=ESCALATION_TOOL_CALL_THRESHOLD
    ) == (
        PRO_MODEL,
        "tool_call_threshold",
    )


def test_below_threshold_stays_on_flash():
    assert _select_model(
        "keep digging", completed_tool_call_rounds=ESCALATION_TOOL_CALL_THRESHOLD - 1
    ) == (FLASH_MODEL, "default")


def test_deeper_analysis_keyword_escalates_immediately():
    assert _select_model(
        "Can you give me a deep dive on Tuesday sales?", completed_tool_call_rounds=0
    ) == (PRO_MODEL, "keyword")


def test_keyword_match_is_case_insensitive():
    assert _select_model("I want a THOROUGH breakdown please", completed_tool_call_rounds=0) == (
        PRO_MODEL,
        "keyword",
    )


def test_keyword_takes_priority_regardless_of_round_count():
    assert _select_model("give me an in-depth analysis", completed_tool_call_rounds=0) == (
        PRO_MODEL,
        "keyword",
    )
