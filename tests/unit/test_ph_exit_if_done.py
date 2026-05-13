"""Verify exit_if_done matches ph_claus.c."""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.exit_if_done import exit_if_done
from dectalk.ph.init_phclause import init_phclause


def test_not_done_returns_false() -> None:
    """``nphone < nallotot`` returns False and doesn't touch arrays."""
    state = DphT()
    init_phclause(state)
    state.nphone = 5
    state.nallotot = 10
    durs, f0, offset = state.user_durs, state.user_f0, state.user_offset
    assert durs is not None
    assert f0 is not None
    assert offset is not None
    durs[0] = 99
    f0[0] = 99
    offset[0] = 99
    state.nsymbtot = 0
    result = exit_if_done(state)
    assert result is False
    assert durs[0] == 99
    assert f0[0] == 99
    assert offset[0] == 99


def test_done_returns_true_and_zeros_arrays() -> None:
    """``nphone >= nallotot`` returns True and zeros arrays up to nsymbtot."""
    state = DphT()
    init_phclause(state)
    state.nphone = 10
    state.nallotot = 10  # nphone >= nallotot triggers exit.
    state.nsymbtot = 4
    durs, f0, offset = state.user_durs, state.user_f0, state.user_offset
    assert durs is not None
    assert f0 is not None
    assert offset is not None
    for i in range(5):
        durs[i] = 99
        f0[i] = 99
        offset[i] = 99
    result = exit_if_done(state)
    assert result is True
    for i in range(5):
        assert durs[i] == 0
        assert f0[i] == 0
        assert offset[i] == 0


def test_done_zeros_inclusive_of_nsymbtot() -> None:
    """The C source uses ``n <= nsymbtot`` — so nsymbtot is included."""
    state = DphT()
    init_phclause(state)
    state.nphone = 1
    state.nallotot = 1
    state.nsymbtot = 2  # Should zero indices 0, 1, 2.
    durs = state.user_durs
    assert durs is not None
    durs[2] = 99
    durs[3] = 99  # outside range — should remain
    exit_if_done(state)
    assert durs[2] == 0
    assert durs[3] == 99


def test_done_with_nphone_greater_than_nallotot() -> None:
    """``nphone > nallotot`` (overshoot) still returns True."""
    state = DphT()
    init_phclause(state)
    state.nphone = 20
    state.nallotot = 5
    assert exit_if_done(state) is True
