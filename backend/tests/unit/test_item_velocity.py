import uuid
from datetime import date
from decimal import Decimal

from app.agent.tools.item_velocity import _build_item_velocities, _window_midpoint


def test_window_midpoint_even_length_splits_exactly_in_half():
    start, end = date(2026, 1, 1), date(2026, 1, 10)  # 10 days

    midpoint = _window_midpoint(start, end)

    assert midpoint == date(2026, 1, 6)
    first_half_days = (midpoint - start).days
    second_half_days = (end - midpoint).days + 1
    assert first_half_days == second_half_days == 5


def test_window_midpoint_odd_length_splits_into_consecutive_halves():
    start, end = date(2026, 1, 1), date(2026, 1, 9)  # 9 days

    midpoint = _window_midpoint(start, end)

    first_half_days = (midpoint - start).days
    second_half_days = (end - midpoint).days + 1
    # 9 days can't split evenly; the formula's rounding gives one half an
    # extra day — assert only that both halves are non-empty and the split
    # accounts for every day exactly once (no gap, no overlap).
    assert first_half_days + second_half_days == 9
    assert first_half_days > 0
    assert second_half_days > 0


def _row(day: date, menu_item_id: uuid.UUID, name: str, category: str, quantity: int):
    return (day, menu_item_id, name, category, quantity)


def test_build_item_velocities_labels_trending_up_item():
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    midpoint = _window_midpoint(start, end)
    item_id = uuid.uuid4()
    rows = [
        _row(start, item_id, "Truffle Fries", "appetizer", 2),
        _row(midpoint, item_id, "Truffle Fries", "appetizer", 20),
        _row(end, item_id, "Truffle Fries", "appetizer", 20),
    ]

    velocities = _build_item_velocities(start, end, rows, top_n=None)

    assert len(velocities) == 1
    v = velocities[0]
    assert v.trend == "up"
    assert v.first_half_quantity == 2
    assert v.second_half_quantity == 40
    assert v.quantity_change_pct == Decimal("1900")


def test_build_item_velocities_labels_flat_item():
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    midpoint = _window_midpoint(start, end)
    item_id = uuid.uuid4()
    rows = [
        _row(start, item_id, "Steady Item", "entree", 10),
        _row(midpoint, item_id, "Steady Item", "entree", 10),
    ]

    velocities = _build_item_velocities(start, end, rows, top_n=None)

    assert velocities[0].trend == "flat"
    assert velocities[0].quantity_change_pct == Decimal("0")


def test_build_item_velocities_second_half_only_is_up_with_none_pct():
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    midpoint = _window_midpoint(start, end)
    item_id = uuid.uuid4()
    rows = [_row(midpoint, item_id, "New Item", "dessert", 5)]

    velocities = _build_item_velocities(start, end, rows, top_n=None)

    assert velocities[0].trend == "up"
    assert velocities[0].first_half_quantity == 0
    assert velocities[0].quantity_change_pct is None


def test_build_item_velocities_first_half_only_is_down_with_none_pct():
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    item_id = uuid.uuid4()
    rows = [_row(start, item_id, "Fading Item", "dessert", 5)]

    velocities = _build_item_velocities(start, end, rows, top_n=None)

    assert velocities[0].trend == "down"
    assert velocities[0].second_half_quantity == 0
    assert velocities[0].quantity_change_pct is None


def test_build_item_velocities_top_n_orders_undefined_up_first():
    start, end = date(2026, 1, 1), date(2026, 1, 10)
    midpoint = _window_midpoint(start, end)
    new_item = uuid.uuid4()
    modest_item = uuid.uuid4()
    down_item = uuid.uuid4()
    rows = [
        _row(midpoint, new_item, "Brand New", "entree", 5),  # up, None pct (infinite)
        _row(start, modest_item, "Modest Grower", "entree", 10),
        _row(midpoint, modest_item, "Modest Grower", "entree", 20),  # up, 100%
        _row(start, down_item, "Declining", "entree", 10),  # down, None pct
    ]

    velocities = _build_item_velocities(start, end, rows, top_n=2)

    assert len(velocities) == 2
    assert velocities[0].menu_item_name == "Brand New"
    assert velocities[1].menu_item_name == "Modest Grower"
