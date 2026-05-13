"""Verify init_pars matches ph_claus.c."""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.init_pars import init_pars


def test_tcum_reset_to_minus_one() -> None:
    """``tcum`` resets to -1 (before any frames)."""
    state = DphT(tcum=100)
    init_pars(state)
    assert state.tcum == -1


def test_nphone_reset_to_minus_one() -> None:
    """``nphone`` resets to -1 (no phoneme selected)."""
    state = DphT(nphone=5)
    init_pars(state)
    assert state.nphone == -1


def test_durfon_reset_to_zero() -> None:
    """``durfon`` resets to 0 (no frames yet)."""
    state = DphT(durfon=10)
    init_pars(state)
    assert state.durfon == 0


def test_openquo_takes_alloopenq_zero() -> None:
    """``openquo`` is seeded from ``alloopenq[0]``."""
    state = DphT()
    state.alloopenq = [42, 0, 0]
    init_pars(state)
    assert state.openquo == 42


def test_openquo_with_empty_alloopenq() -> None:
    """``openquo`` is 0 when ``alloopenq`` is empty (pre-init state)."""
    state = DphT()
    state.alloopenq = []
    init_pars(state)
    assert state.openquo == 0


def test_idempotent() -> None:
    """Calling ``init_pars`` twice produces the same state."""
    state = DphT()
    state.alloopenq = [7]
    init_pars(state)
    first = (state.tcum, state.nphone, state.durfon, state.openquo)
    init_pars(state)
    assert (state.tcum, state.nphone, state.durfon, state.openquo) == first
