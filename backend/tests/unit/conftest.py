from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_restaurant_names():
    """answer_question()/answer_question_stream() fetch restaurant names to
    build a human-readable system instruction (Phase 8 fix — a live /chat
    call answered with raw restaurant_id UUIDs instead of names). Unit tests
    in this directory have no real database, so this stubs the lookup to an
    empty dict by default — build_insights_system_instruction() falls back
    to "name unknown" gracefully, preserving every existing assertion that
    checks for the raw restaurant_id string. Tests that care about the name
    itself patch this explicitly within their own `with` block, which
    overrides this for that scope."""
    with patch("app.agent.insights.get_restaurant_names", AsyncMock(return_value={})):
        yield
