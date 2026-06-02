from __future__ import annotations

import pytest

from src.core.snowflake import (
    EPOCH_MS,
    TIMESTAMP_SHIFT,
    InvalidSystemClock,
    SnowflakeGenerator,
)


def test_node_id_out_of_range_rejected() -> None:
    with pytest.raises(ValueError):
        SnowflakeGenerator(node_id=-1)
    with pytest.raises(ValueError):
        SnowflakeGenerator(node_id=1024)


def test_ten_thousand_ids_are_distinct() -> None:
    gen = SnowflakeGenerator(node_id=0)
    ids = {gen.next_id() for _ in range(10_000)}
    assert len(ids) == 10_000


def test_clock_moving_backwards_raises() -> None:
    t = [1_000_000]
    gen = SnowflakeGenerator(node_id=0, clock=lambda: t[0])
    gen.next_id()  # establishes last_ms
    t[0] = 999_999  # backwards
    with pytest.raises(InvalidSystemClock):
        gen.next_id()


def test_sequence_exhaustion_blocks_until_next_ms() -> None:
    t = 5_000_000
    counter = {"n": 0}
    advance_after_total_calls = 5_000

    def clock() -> int:
        counter["n"] += 1
        if counter["n"] >= advance_after_total_calls:
            return t + 1
        return t

    gen = SnowflakeGenerator(node_id=0, clock=clock)
    issued: set[int] = set()
    for _ in range(4_200):
        issued.add(gen.next_id())
    assert len(issued) == 4_200


def test_id_uses_expected_bit_layout() -> None:
    t = [EPOCH_MS + 1234]
    gen = SnowflakeGenerator(node_id=42, clock=lambda: t[0])
    snowflake = gen.next_id()
    timestamp_part = snowflake >> TIMESTAMP_SHIFT
    assert timestamp_part == 1234
