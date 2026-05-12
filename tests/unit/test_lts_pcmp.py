"""Verify ``lsa_util_pcmp`` parity with lsa_util.c."""

from __future__ import annotations

import pytest

from dectalk.lts import pcmp


def test_exact_match() -> None:
    """Full match returns True."""
    assert pcmp.lsa_util_pcmp([1, 2, 3], b"\x01\x02\x03") is True


def test_prefix_match_with_p_len() -> None:
    """A prefix matches when ``p_len`` is set to the prefix length."""
    assert pcmp.lsa_util_pcmp([1, 2, 3, 4, 5], b"\x01\x02", 2) is True


def test_mismatch_returns_false() -> None:
    """Any byte mismatch returns False."""
    assert pcmp.lsa_util_pcmp([1, 2, 3], b"\x01\x99\x03") is False


def test_short_phone_list_returns_false() -> None:
    """If the list ends before ``p_len`` chars, return False."""
    assert pcmp.lsa_util_pcmp([1, 2], b"\x01\x02\x03") is False


def test_empty_pattern_matches() -> None:
    """An empty pattern matches anything (loop doesn't execute)."""
    assert pcmp.lsa_util_pcmp([1, 2, 3], b"") is True


def test_str_pattern_accepted() -> None:
    """str patterns are Latin-1-encoded."""
    assert pcmp.lsa_util_pcmp([ord("a"), ord("b"), ord("c")], "abc") is True


@pytest.mark.parametrize(
    ("phones", "pattern", "expected"),
    [
        ([0x10, 0x20, 0x30], b"\x10\x20\x30", True),
        ([0x10, 0x20, 0x30], b"\x10\x20", True),  # prefix, p_len default = pattern len
        ([0x10, 0x20, 0x30], b"\x10\x21\x30", False),  # mismatch at index 1
        ([0x10], b"\x10\x20", False),  # phones shorter than pattern
        ([], b"\x10", False),  # empty phones, non-empty pattern
        ([], b"", True),  # both empty
    ],
)
def test_parametric(phones: list[int], pattern: bytes, expected: bool) -> None:
    """Spot-check several phone-list + pattern combos."""
    assert pcmp.lsa_util_pcmp(phones, pattern) is expected


def test_p_len_zero_always_matches() -> None:
    """``p_len=0`` always returns True (loop doesn't execute)."""
    assert pcmp.lsa_util_pcmp([], b"", 0) is True
    assert pcmp.lsa_util_pcmp([1, 2, 3], b"\x99\x99\x99", 0) is True


def test_p_len_larger_than_pattern_clamps_to_no_match() -> None:
    """If ``p_len`` exceeds the pattern length, we can't fulfil it → False."""
    # The C code reads ``p[i]`` past the end of the pattern, which is UB.
    # The Python guard returns False rather than risking an exception or
    # platform-dependent garbage.
    assert pcmp.lsa_util_pcmp([1, 2, 3, 4], b"\x01\x02", 4) is False
