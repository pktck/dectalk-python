"""Verify saveval matches ph_vset.c."""

from __future__ import annotations

from dectalk.include.cmd_codes import SPDEF
from dectalk.ph.dph_t import DphT
from dectalk.ph.saveval import saveval


def test_saveval_copies_curspdef_to_var_val() -> None:
    """``var_val`` mirrors ``curspdef`` after ``saveval``."""
    state = DphT()
    state.curspdef = [i * 10 for i in range(SPDEF)]
    saveval(state)
    assert state.var_val == state.curspdef


def test_saveval_grows_var_val() -> None:
    """``var_val`` is grown to ``SPDEF`` entries if shorter."""
    state = DphT()
    state.curspdef = [1] * SPDEF
    state.var_val = []
    saveval(state)
    assert len(state.var_val) == SPDEF


def test_saveval_uses_zeros_for_missing_curspdef_tail() -> None:
    """If ``curspdef`` is shorter than ``SPDEF``, the tail is zero-filled."""
    state = DphT()
    state.curspdef = [1, 2, 3]
    saveval(state)
    assert state.var_val[:3] == [1, 2, 3]
    assert state.var_val[3:] == [0] * (SPDEF - 3)


def test_saveval_overwrites_existing_var_val() -> None:
    """Existing ``var_val`` content is overwritten by ``curspdef``."""
    state = DphT()
    state.curspdef = [9] * SPDEF
    state.var_val = [42] * SPDEF
    saveval(state)
    assert state.var_val == [9] * SPDEF


def test_saveval_idempotent() -> None:
    """Calling ``saveval`` twice produces the same result."""
    state = DphT()
    state.curspdef = list(range(SPDEF))
    saveval(state)
    first = list(state.var_val)
    saveval(state)
    assert state.var_val == first
