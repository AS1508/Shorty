from __future__ import annotations

import pytest

from src.core.base62 import decode, encode


def test_known_encodings() -> None:
    assert encode(0) == "0"
    assert encode(1) == "1"
    assert encode(35) == "Z"
    assert encode(36) == "a"
    assert encode(61) == "z"
    assert encode(62) == "10"
    assert encode(63) == "11"
    assert encode(4095) == "143"
    assert encode(4096) == "144"


def test_round_trip() -> None:
    for value in [0, 1, 61, 62, 4095, 4096, 2**31 - 1, 2**62, 2**63 - 1]:
        assert decode(encode(value)) == value


def test_decode_invalid_char() -> None:
    with pytest.raises(ValueError):
        decode("abc!def")


def test_decode_empty() -> None:
    with pytest.raises(ValueError):
        decode("")


def test_encode_negative() -> None:
    with pytest.raises(ValueError):
        encode(-1)
