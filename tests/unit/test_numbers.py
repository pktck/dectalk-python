"""Tests for number-to-words conversion."""

from __future__ import annotations

import pytest

from dectalk.kernel.numbers import number_to_words


@pytest.mark.parametrize(
    ("value", "words"),
    [
        (0, ["ZERO"]),
        (1, ["ONE"]),
        (9, ["NINE"]),
        (10, ["TEN"]),
        (11, ["ELEVEN"]),
        (15, ["FIFTEEN"]),
        (19, ["NINETEEN"]),
        (20, ["TWENTY"]),
        (21, ["TWENTY", "ONE"]),
        (99, ["NINETY", "NINE"]),
        (100, ["ONE", "HUNDRED"]),
        (101, ["ONE", "HUNDRED", "ONE"]),
        (123, ["ONE", "HUNDRED", "TWENTY", "THREE"]),
        (1000, ["ONE", "THOUSAND"]),
        (2024, ["TWO", "THOUSAND", "TWENTY", "FOUR"]),
        (12345, ["TWELVE", "THOUSAND", "THREE", "HUNDRED", "FORTY", "FIVE"]),
        (1_000_000, ["ONE", "MILLION"]),
    ],
)
def test_number_to_words(value: int, words: list[str]) -> None:
    assert number_to_words(value) == words


def test_negative_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        number_to_words(-1)


def test_very_large_falls_back_to_digit_by_digit() -> None:
    # > 1e12 -> spelled digit-by-digit (no TRILLION word in the lexicon yet).
    out = number_to_words(10**12 + 5)
    assert out[0] == "ONE"
    assert out[-1] == "FIVE"
