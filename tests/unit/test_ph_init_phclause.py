"""Verify init_phclause zeroes per-clause arrays and seeds window pointers."""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.init_phclause import init_phclause
from dectalk.ph.inton_constants import SAFETY
from dectalk.ph.numeric_constants import NPHON_MAX

_BUF_SIZE = NPHON_MAX + SAFETY + 2


def test_arrays_are_sized_to_buffer() -> None:
    """All 5 per-clause arrays are resized to ``NPHON_MAX + SAFETY + 2``."""
    state = DphT()
    init_phclause(state)
    for name in ("allophons", "allofeats", "allodurs", "f0tar", "f0tim"):
        assert len(getattr(state, name)) == _BUF_SIZE


def test_arrays_are_zeroed() -> None:
    """Every element of every per-clause array is 0."""
    state = DphT()
    init_phclause(state)
    for name in ("allophons", "allofeats", "allodurs", "f0tar", "f0tim"):
        assert all(v == 0 for v in getattr(state, name))


def test_scalar_resets() -> None:
    """``fvvtran`` / ``bvvtran`` are reset to 0."""
    state = DphT(fvvtran=5, bvvtran=7)
    init_phclause(state)
    assert state.fvvtran == 0
    assert state.bvvtran == 0


def test_window_pointers_alias_parent_arrays() -> None:
    """The 5 window-pointer fields alias their parent arrays."""
    state = DphT()
    init_phclause(state)
    assert state.phonemes is state.allophons
    assert state.sentstruc is state.allofeats
    assert state.user_durs is state.allodurs
    assert state.user_f0 is state.f0tar
    assert state.user_offset is state.f0tim


def test_writing_via_window_pointer_visible_in_parent() -> None:
    """Mutating a window-pointer slot is visible in the parent array."""
    state = DphT()
    init_phclause(state)
    assert state.phonemes is not None
    state.phonemes[10] = 42
    assert state.allophons[10] == 42


def test_idempotent_reinit() -> None:
    """Calling ``init_phclause`` twice leaves everything zeroed."""
    state = DphT()
    init_phclause(state)
    assert state.allophons is not None
    state.allophons[0] = 99
    init_phclause(state)
    assert state.allophons[0] == 0
