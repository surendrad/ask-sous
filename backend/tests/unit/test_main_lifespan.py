import asyncio
from types import SimpleNamespace

from app.main import app, lifespan


async def test_lifespan_starts_trickle_loop_when_enabled(monkeypatch):
    calls = []

    async def fake_loop(**kwargs):
        calls.append(1)
        await asyncio.sleep(10)

    monkeypatch.setattr("app.main.run_trickle_loop", fake_loop)
    monkeypatch.setattr("app.main.get_settings", lambda: SimpleNamespace(enable_trickle=True))

    async with lifespan(app):
        await asyncio.sleep(0.01)

    assert calls == [1]


async def test_lifespan_does_not_start_trickle_loop_when_disabled(monkeypatch):
    calls = []

    async def fake_loop(**kwargs):
        calls.append(1)

    monkeypatch.setattr("app.main.run_trickle_loop", fake_loop)
    monkeypatch.setattr("app.main.get_settings", lambda: SimpleNamespace(enable_trickle=False))

    async with lifespan(app):
        await asyncio.sleep(0.01)

    assert calls == []
