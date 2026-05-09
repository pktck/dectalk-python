"""Tests for the rule-based LTS fallback (`dectalk.lts.rules_us`)."""

from __future__ import annotations

import pytest

from dectalk.lts import lts


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("cat", ["K", "AE", "T"]),
        ("dog", ["D", "AA", "G"]),
        ("phone", ["F", "OW", "N"]),
        ("thought", ["TH", "AO", "T"]),
        ("rough", ["R", "AH", "F"]),
        ("caught", ["K", "AO", "T"]),
        ("eight", ["EY", "T"]),
        ("high", ["HH", "AY"]),
        ("nice", ["N", "AY", "S"]),
    ],
)
def test_known_spelling_patterns(word: str, expected: list[str]) -> None:
    assert lts(word) == expected


def test_returns_list_of_strings() -> None:
    result = lts("hello")
    assert isinstance(result, list)
    assert all(isinstance(p, str) for p in result)


def test_case_insensitive() -> None:
    assert lts("hello") == lts("HELLO") == lts("Hello")


def test_empty_string_returns_empty() -> None:
    assert lts("") == []


def test_apostrophes_are_ignored() -> None:
    """Stray apostrophes shouldn't crash; they should be silently skipped."""
    out = lts("can't")
    assert "K" in out
    assert "T" in out
    assert "'" not in out


def test_c_before_e_is_soft() -> None:
    """Soft-c rule: 'cell' starts with S."""
    out = lts("cell")
    assert out[0] == "S"


def test_c_before_a_is_hard() -> None:
    """Hard-c rule: 'cat' starts with K."""
    assert lts("cat")[0] == "K"


def test_qu_pair() -> None:
    out = lts("queen")
    assert out[:2] == ["K", "W"]


def test_silent_e_in_magic_e_word() -> None:
    """Magic-E pattern: 'bake' should be B EY K, not B EY K E."""
    out = lts("bake")
    assert out == ["B", "EY", "K"]


def test_x_expands_to_k_s() -> None:
    out = lts("box")
    assert "K" in out and "S" in out
