from __future__ import annotations

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)
_CHAR_TO_VALUE: dict[str, int] = {ch: i for i, ch in enumerate(ALPHABET)}


def encode(value: int) -> str:
    if value < 0:
        raise ValueError(f"cannot encode negative value: {value}")
    if value == 0:
        return ALPHABET[0]
    chars: list[str] = []
    n = value
    while n > 0:
        n, rem = divmod(n, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def decode(code: str) -> int:
    if not code:
        raise ValueError("cannot decode empty string")
    n = 0
    for ch in code:
        digit = _CHAR_TO_VALUE.get(ch)
        if digit is None:
            raise ValueError(f"invalid base62 character: {ch!r}")
        n = n * BASE + digit
    return n
