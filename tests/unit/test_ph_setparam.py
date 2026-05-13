"""Verify setparam matches ph_vset.c."""

from __future__ import annotations

from dectalk.include.cmd_codes import SPD_OQ, SPD_SEX
from dectalk.include.dectalk import Voice
from dectalk.ph.dph_t import DphT
from dectalk.ph.queue_structs import Limit
from dectalk.ph.setparam import setparam
from dectalk.ph.voice_limits import limit as default_limit


def test_clamps_below_min() -> None:
    """Value below l_min is clamped to l_min."""
    state = DphT()
    setparam(
        state,
        SPD_SEX,
        -999,
        limit_table=default_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=True,
    )
    assert state.curspdef[SPD_SEX] == default_limit[SPD_SEX].l_min


def test_clamps_above_max() -> None:
    """Value above l_max is clamped to l_max."""
    state = DphT()
    setparam(
        state,
        SPD_SEX,
        9999,
        limit_table=default_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=True,
    )
    assert state.curspdef[SPD_SEX] == default_limit[SPD_SEX].l_max


def test_in_range_stored_verbatim() -> None:
    """Value within range is stored verbatim."""
    state = DphT()
    setparam(
        state,
        SPD_SEX,
        0,
        limit_table=default_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=True,
    )
    assert state.curspdef[SPD_SEX] == 0


def test_out_of_range_which_is_noop() -> None:
    """Out-of-range ``which`` is silently ignored."""
    state = DphT()
    state.curspdef = [99] * 40
    setparam(
        state,
        SPD_OQ + 1,
        0,
        limit_table=default_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=True,
    )
    # No change in curspdef.
    assert state.curspdef[SPD_OQ + 1] == 99
    # loadspdef untouched.
    assert state.loadspdef == 0


def test_loadspdef_set_after_write() -> None:
    """``loadspdef`` is set TRUE (=1) after a successful write."""
    state = DphT()
    assert state.loadspdef == 0
    setparam(
        state,
        SPD_SEX,
        0,
        limit_table=default_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=True,
    )
    assert state.loadspdef == 1


def test_tunedef_offset_applied_when_not_tuning() -> None:
    """Tune-table offset is added when autotuning is off + voice != VAL."""
    state = DphT()
    # Set up a tunedef row for voice 0 (Paul).
    tune_row = [0] * 40
    tune_row[SPD_SEX] = 10  # add 10 to SPD_SEX
    state.tunedef = [tune_row]
    # Custom limit table with l_min=0, l_max=100 so the offset fits.
    fake_limit = tuple(Limit(l_min=-50, l_max=50) for _ in range(SPD_OQ + 1))
    setparam(
        state,
        SPD_SEX,
        5,
        limit_table=fake_limit,
        last_voice=0,
        b_do_tuning=False,
    )
    assert state.curspdef[SPD_SEX] == 15  # 5 + 10


def test_tunedef_offset_skipped_for_variable_val() -> None:
    """For Variable Val voice, no tune-offset is applied."""
    state = DphT()
    tune_row = [0] * 40
    tune_row[SPD_SEX] = 10
    state.tunedef = [tune_row] * 11  # voice 10 = VARIABLE_VAL
    fake_limit = tuple(Limit(l_min=-50, l_max=50) for _ in range(SPD_OQ + 1))
    setparam(
        state,
        SPD_SEX,
        5,
        limit_table=fake_limit,
        last_voice=int(Voice.VARIABLE_VAL),
        b_do_tuning=False,
    )
    assert state.curspdef[SPD_SEX] == 5  # no offset added
