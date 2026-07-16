import uuid

import pytest

from app.seed.embed_seed_data import _build_update_payloads, _chunk


def test_chunk_shorter_than_size_yields_one_chunk():
    chunks = list(_chunk([1, 2, 3], size=10))
    assert chunks == [[1, 2, 3]]


def test_chunk_exactly_divisible_yields_equal_chunks():
    chunks = list(_chunk(list(range(10)), size=5))
    assert chunks == [list(range(5)), list(range(5, 10))]


def test_chunk_with_remainder_yields_shorter_final_chunk():
    chunks = list(_chunk(list(range(7)), size=3))
    assert chunks == [[0, 1, 2], [3, 4, 5], [6]]


def test_chunk_full_scale_yields_two_chunks():
    chunks = list(_chunk(list(range(138)), size=100))
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert len(chunks[1]) == 38


def test_build_update_payloads_pairs_ids_and_vectors_in_order():
    ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    vectors = [[0.1], [0.2], [0.3]]

    payloads = _build_update_payloads(ids, vectors)

    assert payloads == [
        {"row_id": ids[0], "embedding": [0.1]},
        {"row_id": ids[1], "embedding": [0.2]},
        {"row_id": ids[2], "embedding": [0.3]},
    ]


def test_build_update_payloads_length_mismatch_raises():
    with pytest.raises(ValueError):
        _build_update_payloads([uuid.uuid4(), uuid.uuid4()], [[0.1]])
