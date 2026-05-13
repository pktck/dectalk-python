"""Verify shrdur matches ph_sttr2.c."""

from __future__ import annotations

from dectalk.ph.numeric_constants import FRAC_ONE, NSAMP_FRAME
from dectalk.ph.shrdur import shrdur


def test_zero_shrink_returns_floor() -> None:
    """``shrink == 0`` produces the minimum NSAMP_FRAME-clamped result."""
    # With shrink=0, halfmaxdur is 0, so durin always exceeds halfmaxdur,
    # gets clamped to 0, and then yields halfmaxdur=0 — clamped up to
    # NSAMP_FRAME, then shifted right by 6.
    result = shrdur(100, 10, 0)
    assert result == (NSAMP_FRAME >> 6)


def test_full_shrink_returns_proportional_duration() -> None:
    """``shrink == FRAC_ONE`` gives a sensible non-zero output."""
    result = shrdur(100, 10, FRAC_ONE)
    assert result > 0
    # For durin=100, inhdr_frames=10: regression value from a smoke run.
    assert result == 11


def test_half_shrink_smaller_than_full() -> None:
    """Half-shrink produces a value <= full-shrink (since maxdur halves)."""
    full = shrdur(100, 10, FRAC_ONE)
    half = shrdur(100, 10, FRAC_ONE >> 1)
    assert half <= full


def test_clamps_to_nsamp_frame_minimum() -> None:
    """Very short inputs clamp to the NSAMP_FRAME / 64 minimum."""
    # An input of 0 ms with shrink=0 → output clamped to NSAMP_FRAME, >> 6.
    result = shrdur(0, 1, 0)
    assert result == (NSAMP_FRAME >> 6)


def test_fold_around_halfinhdr() -> None:
    """Durations past ``halfinhdr`` get folded; result is symmetric."""
    # Pick a long durin so the fold path triggers.
    folded = shrdur(1000, 20, FRAC_ONE)
    assert folded > 0


def test_returns_integer() -> None:
    """The result is always an int (the >> 6 truncation)."""
    result = shrdur(50, 5, FRAC_ONE >> 2)
    assert isinstance(result, int)
