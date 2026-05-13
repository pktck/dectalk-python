"""Verify raise_last_stress matches ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1, S2, SEMPH
from dectalk.ph.dph_t import DphT
from dectalk.ph.raise_last_stress import raise_last_stress


def test_promotes_latest_s1_to_semph() -> None:
    """The most recent S1 before msym becomes SEMPH."""
    state = DphT()
    state.symbols = [0, S1, S2, S1, 0]
    raise_last_stress(state, 4)
    # Most recent S1 at index 3 → promoted to SEMPH.
    assert state.symbols[3] == SEMPH
    # Earlier S1 at index 1 → untouched.
    assert state.symbols[1] == S1


def test_no_s1_no_change() -> None:
    """If no S1 is found before msym, the symbols are unchanged."""
    state = DphT()
    state.symbols = [0, S2, S2, S2]
    raise_last_stress(state, 3)
    assert state.symbols == [0, S2, S2, S2]


def test_index_zero_is_never_promoted() -> None:
    """Index 0 is excluded from the walk (m > 0 guard)."""
    state = DphT()
    state.symbols = [S1, S2]
    raise_last_stress(state, 1)
    # Index 0 has S1 but m > 0 guard excludes it.
    assert state.symbols[0] == S1


def test_promotes_only_one() -> None:
    """Only the latest S1 is promoted; earlier ones stay."""
    state = DphT()
    state.symbols = [0, S1, S1, S1, 0]
    raise_last_stress(state, 4)
    # Index 3 (most recent S1) is promoted.
    assert state.symbols[3] == SEMPH
    # Earlier S1s stay.
    assert state.symbols[1] == S1
    assert state.symbols[2] == S1


def test_handles_empty_symbols() -> None:
    """An empty ``symbols`` list is a no-op (defensive)."""
    state = DphT()
    state.symbols = []
    raise_last_stress(state, 5)  # Should not raise.


def test_msym_one_walks_no_indices() -> None:
    """When msym=1, the range(0, 0, -1) is empty; no change."""
    state = DphT()
    state.symbols = [S1, S1]
    raise_last_stress(state, 1)
    # The walk is range(0, 0, -1) which is empty.
    assert state.symbols == [S1, S1]
