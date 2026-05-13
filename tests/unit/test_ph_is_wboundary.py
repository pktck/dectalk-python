"""Verify is_wboundary matches ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import (
    COMMA,
    EXCLAIM,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    SBOUND,
    VPSTART,
    WBOUND,
)
from dectalk.ph.is_wboundary import is_wboundary


def test_wbound_is_boundary() -> None:
    """``WBOUND`` (lowest boundary) returns True."""
    assert is_wboundary(WBOUND) is True


def test_exclaim_is_boundary() -> None:
    """``EXCLAIM`` (highest boundary) returns True."""
    assert is_wboundary(EXCLAIM) is True


def test_punctuation_codes_are_boundary() -> None:
    """All punctuation codes between WBOUND and EXCLAIM return True."""
    for code in (PPSTART, VPSTART, RELSTART, COMMA, PERIOD, QUEST):
        assert is_wboundary(code) is True


def test_sbound_is_not_boundary() -> None:
    """SBOUND (< WBOUND) is not a word-boundary."""
    assert is_wboundary(SBOUND) is False


def test_zero_is_not_boundary() -> None:
    """Code 0 (SIL) is not a word-boundary."""
    assert is_wboundary(0) is False


def test_codes_past_exclaim_not_boundary() -> None:
    """Codes above EXCLAIM (e.g. NEW_PARAGRAPH at 119) aren't boundaries."""
    assert is_wboundary(EXCLAIM + 1) is False
    assert is_wboundary(255) is False
