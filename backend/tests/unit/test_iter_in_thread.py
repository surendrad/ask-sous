import pytest

from app.agent.llm_client import _iter_in_thread


async def test_yields_items_in_order():
    def gen():
        yield 1
        yield 2
        yield 3

    collected = [item async for item in _iter_in_thread(gen())]

    assert collected == [1, 2, 3]


async def test_empty_iterable_yields_nothing():
    def gen():
        return
        yield  # pragma: no cover - makes this a generator function

    collected = [item async for item in _iter_in_thread(gen())]

    assert collected == []


async def test_mid_iteration_exception_propagates_to_consumer():
    def gen():
        yield "a"
        raise ValueError("boom")

    collected = []
    with pytest.raises(ValueError, match="boom"):
        async for item in _iter_in_thread(gen()):
            collected.append(item)

    assert collected == ["a"]
