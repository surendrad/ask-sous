import pytest
import sqlglot

from app.agent.tools.raw_sql import MAX_ROWS, _enforce_row_cap, _validate_select_only


def test_plain_select_passes():
    _validate_select_only("SELECT * FROM transactions WHERE restaurant_id = :restaurant_id")


def test_select_with_bind_params_passes():
    _validate_select_only(
        "SELECT total_amount FROM transactions WHERE restaurant_id = :restaurant_id "
        "AND transaction_time > :since"
    )


def test_stacked_drop_after_select_raises():
    with pytest.raises(ValueError):
        _validate_select_only("SELECT 1; DROP TABLE restaurants")


def test_bare_drop_raises():
    with pytest.raises(ValueError):
        _validate_select_only("DROP TABLE restaurants")


def test_update_raises():
    with pytest.raises(ValueError):
        _validate_select_only("UPDATE transactions SET total_amount = 0")


def test_select_into_raises():
    with pytest.raises(ValueError):
        _validate_select_only("SELECT * INTO new_table FROM transactions")


def test_delete_hidden_in_cte_raises():
    with pytest.raises(ValueError):
        _validate_select_only("WITH x AS (DELETE FROM transactions RETURNING *) SELECT * FROM x")


def test_enforce_row_cap_wraps_query_with_outer_limit():
    wrapped = _enforce_row_cap("SELECT * FROM transactions", max_rows=50)
    parsed = sqlglot.parse_one(wrapped, dialect="postgres")
    assert str(parsed.args["limit"].expression) == "50"


def test_enforce_row_cap_outer_limit_wins_over_existing_inner_limit():
    # The inner LIMIT 10000 is left untouched (we wrap rather than rewrite
    # its AST), but the outer LIMIT is always the smaller, enforced cap —
    # so the effective result set is bounded by max_rows regardless.
    wrapped = _enforce_row_cap("SELECT * FROM transactions LIMIT 10000", max_rows=MAX_ROWS)
    parsed = sqlglot.parse_one(wrapped, dialect="postgres")
    assert str(parsed.args["limit"].expression) == str(MAX_ROWS)
    assert MAX_ROWS < 10000
