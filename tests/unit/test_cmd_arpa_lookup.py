"""Verify ``cm_phon_lookup_arpa`` parity with cm_phon.c."""

from __future__ import annotations

import pytest

from dectalk.cmd.arpa_lookup import cm_phon_lookup_arpa


@pytest.mark.parametrize(
    ("ph1", "ph2"),
    [("i", "y"), ("e", "h"), ("a", "a"), ("a", "y"), ("a", "w"), ("a", "h")],
)
def test_two_byte_match(ph1: str, ph2: str) -> None:
    """A valid 2-byte ARPA pair returns (2, code)."""
    m, c = cm_phon_lookup_arpa(ord(ph1), ord(ph2))
    assert m == 2
    assert c >= 0


def test_case_insensitive_match() -> None:
    """Upper-case input is lower-folded by default."""
    m, c = cm_phon_lookup_arpa(ord("I"), ord("Y"))
    assert m == 2
    assert c >= 0


def test_case_sensitive_no_match() -> None:
    """case_sensitive=True suppresses lower-folding."""
    m, _ = cm_phon_lookup_arpa(ord("I"), ord("Y"), case_sensitive=True)
    # The arpa table only has lower-case entries — IY won't match.
    assert m == 0


def test_no_match() -> None:
    """An unknown 2-byte sequence returns (0, -1)."""
    m, c = cm_phon_lookup_arpa(ord("x"), ord("y"))
    assert m == 0
    assert c == -1


def test_single_byte_match() -> None:
    """A single-byte entry (paired with space) matches when ph2=space."""
    # R is encoded as 'r ' in the arpa table.
    m, c = cm_phon_lookup_arpa(ord("r"), ord(" "))
    assert m == 2  # exact 2-byte match against 'r '
    assert c >= 0


def test_custom_arpa_table() -> None:
    """Callers can pass their own ARPA table."""
    custom = b"abcde "
    # 'ab' is at slot 0
    m, c = cm_phon_lookup_arpa(ord("a"), ord("b"), arpa=custom)
    assert (m, c) == (2, 0)
    # 'e' alone matches via 'e space' at slot 2
    m, c = cm_phon_lookup_arpa(ord("e"), ord(" "), arpa=custom)
    assert (m, c) == (2, 2)
    # 'ex' doesn't match exactly but 'e' matches at slot 2 → 1-byte fallback
    m, c = cm_phon_lookup_arpa(ord("e"), ord("x"), arpa=custom)
    assert (m, c) == (1, 2)
