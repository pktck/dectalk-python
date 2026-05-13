"""Verify get_phone matches ph_setar.c."""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.utterance_constants import GEN_SIL


def test_in_range_returns_phone() -> None:
    """Pointer in [0, nallotot) returns the phone."""
    state = DphT()
    state.allophons = [10, 20, 30, 40]
    state.nallotot = 4
    assert get_phone(state, 0) == 10
    assert get_phone(state, 2) == 30
    assert get_phone(state, 3) == 40


def test_negative_pointer_returns_gen_sil() -> None:
    """Negative pointer yields GEN_SIL."""
    state = DphT()
    state.allophons = [10, 20]
    state.nallotot = 2
    assert get_phone(state, -1) == GEN_SIL
    assert get_phone(state, -100) == GEN_SIL


def test_pointer_at_nallotot_returns_gen_sil() -> None:
    """Pointer == nallotot is out of range."""
    state = DphT()
    state.allophons = [10, 20]
    state.nallotot = 2
    assert get_phone(state, 2) == GEN_SIL


def test_pointer_beyond_nallotot_returns_gen_sil() -> None:
    """Pointer well past nallotot yields GEN_SIL."""
    state = DphT()
    state.allophons = [10, 20]
    state.nallotot = 2
    assert get_phone(state, 5) == GEN_SIL
    assert get_phone(state, 999) == GEN_SIL


def test_empty_allophons_yields_gen_sil() -> None:
    """An empty allophons buffer yields GEN_SIL for any pointer."""
    state = DphT()
    state.allophons = []
    state.nallotot = 0
    assert get_phone(state, 0) == GEN_SIL


def test_allophons_shorter_than_nallotot() -> None:
    """Defensive: pointer in range but past list end still returns GEN_SIL.

    (The C source would index past the array; Python's bounds check
    catches this and falls back to GEN_SIL.)
    """
    state = DphT()
    state.allophons = [10]  # Only one entry.
    state.nallotot = 5  # Lies about array size.
    assert get_phone(state, 0) == 10
    assert get_phone(state, 3) == GEN_SIL  # No undefined behaviour.
