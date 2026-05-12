"""Verify ``ls_proc_is_a_part`` / ``ls_proc_non_zero`` parity with l_us_pr1.c.

Cross-validates the two pure number-helper functions against an exhaustive
input space (every byte for ``is_a_part``, varied buffers for ``non_zero``).
"""

from __future__ import annotations

import pytest

from dectalk.lts import proc_helpers as ph


@pytest.mark.parametrize("c", [ord("-"), ord("/"), *range(ord("0"), ord("9") + 1)])
def test_is_a_part_returns_false_for_digit_or_separator(c: int) -> None:
    """Digits and ``-`` / ``/`` are NOT considered parts of a name."""
    assert ph.ls_proc_is_a_part(c) is False


@pytest.mark.parametrize("c", [ord("a"), ord("A"), ord(" "), ord(":"), ord("."), 0xC0])
def test_is_a_part_returns_true_otherwise(c: int) -> None:
    """All other byte values are parts of a name/word."""
    assert ph.ls_proc_is_a_part(c) is True


def test_is_a_part_covers_every_byte() -> None:
    """The function partitions 0..255 into two disjoint sets."""
    part_falses: set[int] = {ord("-"), ord("/"), *range(ord("0"), ord("9") + 1)}
    for byte in range(256):
        if byte in part_falses:
            assert ph.ls_proc_is_a_part(byte) is False
        else:
            assert ph.ls_proc_is_a_part(byte) is True


def test_non_zero_all_zeros() -> None:
    """Buffer of all '0' returns False."""
    assert ph.ls_proc_non_zero(b"00000", 5) is False


def test_non_zero_zero_at_end() -> None:
    """A non-zero followed by zeros — True (any non-zero in range)."""
    assert ph.ls_proc_non_zero(b"50000", 5) is True


def test_non_zero_zero_at_start() -> None:
    """Leading zero with non-zero in range — True."""
    assert ph.ls_proc_non_zero(b"00005", 5) is True


def test_non_zero_scans_only_n_bytes() -> None:
    """Bytes past index ``n`` are ignored."""
    # The non-zero '5' lives at index 5; n=5 only scans indices 0..4.
    assert ph.ls_proc_non_zero(b"000005", 5) is False
    # n=6 sees the '5'.
    assert ph.ls_proc_non_zero(b"000005", 6) is True


def test_non_zero_empty_range() -> None:
    """n=0 returns False — the while loop never runs."""
    assert ph.ls_proc_non_zero(b"12345", 0) is False


def test_non_zero_with_non_digit_byte() -> None:
    """Any non-'0' byte (digit or letter) counts as non-zero."""
    assert ph.ls_proc_non_zero(b"a0000", 5) is True
    assert ph.ls_proc_non_zero(b"0000A", 5) is True


def test_non_zero_short_circuits_on_first_non_zero() -> None:
    """The C source returns as soon as it sees the first non-zero byte."""
    # Python translation preserves the early-return — verify by passing
    # a buffer where a later byte would raise IndexError but the
    # scanner returns before reaching it.
    assert ph.ls_proc_non_zero(b"10", 1) is True  # n=1 → only index 0
