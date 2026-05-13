"""Verify cmd_init / free_cmd_thread_memory mirror cmd_init.c."""

from __future__ import annotations

from types import SimpleNamespace

from dectalk.cmd.cmd_init import cmd_init, free_cmd_thread_memory
from dectalk.cmd.cmd_states import (
    PHONEME_OFF,
    PHONEME_SPEAK,
    ERROR_speak,
    PUNCT_some,
)
from dectalk.cmd.cmd_t import CmdT


def _make_ksd() -> SimpleNamespace:
    """Stand-in for the unported KSD_T - any object with the attrs we set."""
    return SimpleNamespace(phoneme_mode=0, pitch_delta=0)


def test_cmd_init_calls_reset_comm() -> None:
    """``cmd_init`` performs the parser reset (clears next_char etc.)."""
    state = CmdT(next_char=99, param_index=7)
    ksd = _make_ksd()
    cmd_init(state, ksd, b_reset_all=False, total_commands=5)
    assert state.next_char == 0
    assert state.param_index == 0


def test_cmd_init_reset_all_sets_mode_defaults() -> None:
    """With ``b_reset_all=True`` the kernel-mode defaults are written."""
    state = CmdT()
    ksd = _make_ksd()
    cmd_init(state, ksd, b_reset_all=True, total_commands=5)
    assert ksd.phoneme_mode == (PHONEME_OFF | PHONEME_SPEAK)
    assert state.error_mode == ERROR_speak
    assert state.punct_mode == PUNCT_some
    assert state.last_punct == 0
    assert ksd.pitch_delta == 35


def test_cmd_init_no_reset_keeps_mode_alone() -> None:
    """With ``b_reset_all=False`` the engine-mode fields are untouched."""
    state = CmdT(error_mode=99, punct_mode=88, last_punct=77)
    ksd = SimpleNamespace(phoneme_mode=42, pitch_delta=99)
    cmd_init(state, ksd, b_reset_all=False, total_commands=5)
    assert ksd.phoneme_mode == 42
    assert state.error_mode == 99
    assert state.punct_mode == 88
    assert state.last_punct == 77
    assert ksd.pitch_delta == 99


def test_free_cmd_thread_memory_clears_buffers() -> None:
    """``free_cmd_thread_memory`` clears ``cm`` and ``esc_seq``."""
    state = CmdT()
    state.cm = [1, 2, 3]
    state.esc_seq = object()
    free_cmd_thread_memory(state)
    assert state.cm == []
    assert state.esc_seq is None
