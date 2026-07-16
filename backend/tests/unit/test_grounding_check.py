from app.agent.insights import ToolCallRecord, _check_grounding

_TOOL_CALL = ToolCallRecord(tool_name="get_revenue_summary", arguments={}, result={}, error=None)


def test_answer_with_digits_and_tool_calls_is_grounded():
    assert _check_grounding("Revenue was $500.", [_TOOL_CALL]) is True


def test_answer_with_digits_and_no_tool_calls_is_not_grounded():
    assert _check_grounding("Revenue was $500.", []) is False


def test_answer_with_no_digits_and_no_tool_calls_is_grounded():
    assert _check_grounding("I can compare any two dates for you.", []) is True
