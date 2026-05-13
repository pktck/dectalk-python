"""Verify init_clause matches ph_claus.c."""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.init_clause import init_clause


def test_first_call_initialises_ph_init() -> None:
    """First call sets ph_init=1 and forces loadspdef=TRUE."""
    state = DphT()
    assert state.ph_init == 0
    init_clause(state)
    assert state.ph_init == 1
    assert state.loadspdef == 1


def test_first_call_primes_nf0ev_negative_two() -> None:
    """First call (which sets loadspdef=TRUE) primes nf0ev=-2."""
    state = DphT()
    init_clause(state)
    assert state.nf0ev == -2


def test_subsequent_call_with_loadspdef_off_primes_nf0ev_negative_one() -> None:
    """When loadspdef is FALSE, nf0ev = -1 (weak init)."""
    state = DphT()
    state.ph_init = 1  # Skip first-call path.
    state.loadspdef = 0
    init_clause(state)
    assert state.nf0ev == -1


def test_subsequent_call_with_loadspdef_on_primes_nf0ev_negative_two() -> None:
    """When loadspdef is TRUE on a non-first call, nf0ev = -2."""
    state = DphT()
    state.ph_init = 1
    state.loadspdef = 1
    init_clause(state)
    assert state.nf0ev == -2


def test_first_call_with_loadspdef_pre_set_is_idempotent() -> None:
    """First call doesn't clear an already-true loadspdef."""
    state = DphT()
    state.loadspdef = 1
    init_clause(state)
    assert state.loadspdef == 1
    assert state.ph_init == 1


def test_does_not_change_other_fields() -> None:
    """Fields unrelated to clause init aren't disturbed."""
    state = DphT()
    state.sprate = 200
    state.nallotot = 5
    init_clause(state)
    assert state.sprate == 200
    assert state.nallotot == 5
