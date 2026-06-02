from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from time import time_ns

EPOCH_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z
TIMESTAMP_BITS = 41
NODE_BITS = 10
SEQUENCE_BITS = 12
MAX_SEQUENCE = 1 << SEQUENCE_BITS  # 4096
MAX_NODE = 1 << NODE_BITS  # 1024
TIMESTAMP_SHIFT = NODE_BITS + SEQUENCE_BITS
NODE_SHIFT = SEQUENCE_BITS
SEQUENCE_MASK = MAX_SEQUENCE - 1


class InvalidSystemClock(Exception):
    """Raised when the wall clock moves backwards relative to the last issued timestamp."""


class SnowflakeGenerator:
    """In-process 64-bit Snowflake ID generator.

    Layout: 41 bits ms-since-epoch | 10 bits node | 12 bits sequence.
    """

    def __init__(
        self,
        node_id: int,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        if not 0 <= node_id < MAX_NODE:
            raise ValueError(f"node_id must be in [0, {MAX_NODE}), got {node_id}")
        self._node_id = node_id
        self._clock: Callable[[], int] = clock or self._default_clock
        self._last_ms: int = -1
        self._sequence: int = 0
        self._lock = Lock()

    def _default_clock(self) -> int:
        return time_ns() // 1_000_000

    def next_id(self) -> int:
        with self._lock:
            now_ms = self._clock()

            if now_ms < self._last_ms:
                raise InvalidSystemClock(
                    f"clock moved backwards: now_ms={now_ms} < last_ms={self._last_ms}"
                )

            if now_ms == self._last_ms:
                self._sequence = (self._sequence + 1) & SEQUENCE_MASK
                if self._sequence == 0:
                    now_ms = self._wait_next_ms(self._last_ms)
                    self._last_ms = now_ms
            else:
                self._last_ms = now_ms
                self._sequence = 0

            return (
                (now_ms - EPOCH_MS) << TIMESTAMP_SHIFT
                | (self._node_id << NODE_SHIFT)
                | self._sequence
            )

    def _wait_next_ms(self, previous_ms: int) -> int:
        while True:
            now_ms = self._clock()
            if now_ms > previous_ms:
                return now_ms
