"""Verify cm_pars_new_state / cm_cmd_reset_comm match cm_pars.c / cm_cmd.c."""

from __future__ import annotations

from dectalk.cmd.cmd_states import (
    STATE_BRACKET,
    STATE_COMMAND,
    STATE_KEEP,
    STATE_NORMAL,
    STATE_PARAM,
    STATE_TOSS,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.parser_state import cm_cmd_reset_comm, cm_pars_new_state
from dectalk.include.dectalk import NPARAM


def test_new_state_clears_counters() -> None:
    """``cm_pars_new_state`` zeros ``p_count`` and ``cmd_p_flag``."""
    state = CmdT(p_count=5, cmd_p_flag=3)
    cm_pars_new_state(state, STATE_COMMAND)
    assert state.p_count == 0
    assert state.cmd_p_flag == 0
    assert state.parse_state == STATE_COMMAND


def test_new_state_param_to_param_increments_index() -> None:
    """Re-entering ``STATE_PARAM`` from ``STATE_PARAM`` bumps ``param_index``."""
    state = CmdT(parse_state=STATE_PARAM, param_index=3)
    cm_pars_new_state(state, STATE_PARAM)
    assert state.param_index == 4
    assert state.parse_state == STATE_PARAM


def test_new_state_param_from_other_does_not_increment() -> None:
    """Entering ``STATE_PARAM`` from a different state does not bump."""
    state = CmdT(parse_state=STATE_BRACKET, param_index=3)
    cm_pars_new_state(state, STATE_PARAM)
    assert state.param_index == 3


def test_new_state_toss_after_close_bracket_becomes_normal() -> None:
    """``STATE_TOSS`` after ``']'`` is rewritten to ``STATE_NORMAL``."""
    state = CmdT(last_char=ord("]"))
    cm_pars_new_state(state, STATE_TOSS)
    assert state.parse_state == STATE_NORMAL


def test_new_state_toss_after_other_char_is_toss() -> None:
    """``STATE_TOSS`` after some other char installs ``STATE_TOSS``."""
    state = CmdT(last_char=ord("x"))
    cm_pars_new_state(state, STATE_TOSS)
    assert state.parse_state == STATE_TOSS


def test_reset_comm_clears_state() -> None:
    """``cm_cmd_reset_comm`` resets all per-command scratch counters."""
    state = CmdT(
        next_char=10,
        param_index=5,
        cmd_p_flag=1,
        q_flag=1,
        p_count=3,
        international_flag=2,
        international_temp=7,
    )
    cm_cmd_reset_comm(state, STATE_NORMAL, total_commands=5)
    assert state.next_char == 0
    assert state.param_index == 0
    assert state.cmd_p_flag == 0
    assert state.q_flag == 0
    assert state.p_count == 0
    assert state.international_flag == -1
    assert state.international_temp == 0
    assert state.international_phon_lang == -1


def test_reset_comm_sets_defaults_to_true() -> None:
    """``defaults[0..NPARAM-1]`` is set to TRUE (1) when not ``STATE_KEEP``."""
    state = CmdT()
    cm_cmd_reset_comm(state, STATE_NORMAL, total_commands=3)
    assert len(state.defaults) >= NPARAM
    for i in range(NPARAM):
        assert state.defaults[i] == 1


def test_reset_comm_clears_match_array() -> None:
    """``cm[0..total_commands-1]`` is zeroed when not ``STATE_KEEP``."""
    state = CmdT()
    cm_cmd_reset_comm(state, STATE_NORMAL, total_commands=5)
    assert state.total_matches == 5
    assert state.cm[:5] == [0, 0, 0, 0, 0]


def test_reset_comm_state_keep_preserves_match_array() -> None:
    """``STATE_KEEP`` skips the defaults / cm reset."""
    state = CmdT(total_matches=42, format_index=99, p_count=5)
    state.defaults = [0] * NPARAM
    state.cm = [7, 8, 9]
    cm_cmd_reset_comm(state, STATE_KEEP, total_commands=3)
    # Match array preserved.
    assert state.cm == [7, 8, 9]
    assert state.total_matches == 42
    assert state.format_index == 99
    # But cursors still reset.
    assert state.p_count == 0
    assert state.next_char == 0
