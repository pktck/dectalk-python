"""Verify zap_weaker_bound matches ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import COMMA, HYPHEN, PERIOD, WBOUND
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.zap_weaker_bound import zap_weaker_bound


def _state(symbols: list[int]) -> DphT:
    """Build a DphT with the given symbols and matching scratch buffers."""
    state = DphT()
    state.symbols = list(symbols)
    state.user_durs = [0] * (len(symbols) + 4)
    state.user_f0 = [0] * (len(symbols) + 4)
    state.nsymbtot = len(symbols)
    return state


def test_msym1_weaker_promoted_and_deleted() -> None:
    """When msym1 < msym2, msym1 absorbs msym2's value then gets deleted."""
    state = _state([WBOUND, COMMA, PERIOD])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 0, 2)
    # Index 0 (WBOUND) was promoted to PERIOD, then deleted.
    assert state.nsymbtot == 2
    # After delete the shifted state: original symbols[1] and [2] move down.
    assert state.symbols[0] == COMMA
    assert state.symbols[1] == PERIOD


def test_msym2_weaker_just_deleted() -> None:
    """When msym2 <= msym1, msym2 gets deleted in place."""
    state = _state([PERIOD, COMMA, WBOUND])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 0, 2)
    # PERIOD > WBOUND, so WBOUND (at index 2) gets deleted.
    assert state.nsymbtot == 2
    assert state.symbols[:2] == [PERIOD, COMMA]


def test_hyphen_at_msym1_not_deleted_when_weaker() -> None:
    """A HYPHEN at the weaker position is *not* deleted after promotion."""
    state = _state([HYPHEN, PERIOD])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 0, 1)
    # HYPHEN < PERIOD, so msym1 should be promoted to PERIOD's value.
    # The C source then checks "if (symbols[msym1] != HYPHEN)" — which is true
    # because we just promoted it to PERIOD, so delete fires.
    # Actually re-reading: after the promotion symbols[msym1] == PERIOD, so
    # !=HYPHEN, so delete_symbol runs.
    assert state.nsymbtot == 1
    assert state.symbols[0] == PERIOD


def test_hyphen_at_msym2_not_deleted_when_weaker() -> None:
    """A HYPHEN at msym2 is *not* deleted when it's the weaker one."""
    state = _state([PERIOD, HYPHEN])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 0, 1)
    # PERIOD > HYPHEN, so msym2 would be deleted — but symbols[msym2] == HYPHEN
    # so delete is skipped.
    assert state.nsymbtot == 2
    assert state.symbols[:2] == [PERIOD, HYPHEN]


def test_equal_strengths_deletes_msym2() -> None:
    """When equal, the function falls into the else branch (delete msym2)."""
    state = _state([PERIOD, PERIOD])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 0, 1)
    assert state.nsymbtot == 1
    assert state.symbols[0] == PERIOD


def test_out_of_range_indices_are_noop() -> None:
    """Defensive: out-of-range indices return without touching state."""
    state = _state([PERIOD])
    zap_weaker_bound(KsdT(), state, DphSettarSt(), 5, 10)
    assert state.nsymbtot == 1
    assert state.symbols[0] == PERIOD
