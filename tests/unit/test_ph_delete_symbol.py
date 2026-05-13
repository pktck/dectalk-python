"""Verify delete_symbol matches ph_sort.c."""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.delete_symbol import delete_symbol
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT


def test_shifts_symbols_down() -> None:
    """Symbols after msym shift down by one position."""
    state = DphT()
    state.symbols = [10, 20, 30, 40, 50, 0, 0]
    state.user_durs = [1, 2, 3, 4, 5, 0, 0]
    state.user_f0 = [100, 200, 300, 400, 500, 0, 0]
    state.nsymbtot = 5
    settar = DphSettarSt()
    delete_symbol(KsdT(), state, settar, 1)
    # Index 1 (was 20) is deleted; 30, 40, 50 shift down.
    assert state.symbols[:4] == [10, 30, 40, 50]
    assert state.user_durs[:4] == [1, 3, 4, 5]
    assert state.user_f0[:4] == [100, 300, 400, 500]


def test_decrements_nsymbtot() -> None:
    """``nsymbtot`` drops by 1."""
    state = DphT()
    state.symbols = [1, 2, 3, 0]
    state.user_durs = [0, 0, 0, 0]
    state.user_f0 = [0, 0, 0, 0]
    state.nsymbtot = 3
    delete_symbol(KsdT(), state, DphSettarSt(), 1)
    assert state.nsymbtot == 2


def test_sets_did_del_flag() -> None:
    """``did_del`` flag is set after the delete."""
    state = DphT()
    state.symbols = [1, 2, 0]
    state.user_durs = [0, 0, 0]
    state.user_f0 = [0, 0, 0]
    state.nsymbtot = 2
    settar = DphSettarSt()
    delete_symbol(KsdT(), state, settar, 0)
    assert settar.did_del == 1


def test_delete_last_symbol_no_shift() -> None:
    """Deleting the last symbol just decrements nsymbtot."""
    state = DphT()
    state.symbols = [10, 20, 30, 0]
    state.user_durs = [1, 2, 3, 0]
    state.user_f0 = [100, 200, 300, 0]
    state.nsymbtot = 3
    delete_symbol(KsdT(), state, DphSettarSt(), 2)
    assert state.nsymbtot == 2
    # Symbols up to nsymbtot unchanged.
    assert state.symbols[:2] == [10, 20]


def test_delete_first_symbol_shifts_all() -> None:
    """Deleting index 0 shifts everything down."""
    state = DphT()
    state.symbols = [10, 20, 30, 0]
    state.user_durs = [1, 2, 3, 0]
    state.user_f0 = [0, 0, 0, 0]
    state.nsymbtot = 3
    delete_symbol(KsdT(), state, DphSettarSt(), 0)
    assert state.symbols[:2] == [20, 30]
    assert state.user_durs[:2] == [2, 3]
