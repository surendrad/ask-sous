import asyncio
from unittest.mock import AsyncMock, patch

from app.seed.trickle import run_trickle_loop


async def test_a_failed_tick_does_not_kill_the_loop():
    tick = AsyncMock(side_effect=[RuntimeError("transient DB error"), None, None])

    with patch("app.seed.trickle._tick", tick):
        task = asyncio.create_task(run_trickle_loop(interval_seconds=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # The loop kept calling _tick after the first one raised, instead of
    # the task dying silently on the first failure.
    assert tick.await_count >= 2
