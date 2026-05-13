"""Verify cm_cmd_remove matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_remove import cm_cmd_remove
from dectalk.cmd.cmd_states import CMD_success
from dectalk.include.cmd_codes import KILL_TASK
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english


def test_clears_lang_english_ready_bit() -> None:
    """``lang_ready[LANG_english]`` is zeroed unconditionally."""
    ksd = KsdT()
    ksd.lang_ready[LANG_english] = 0xFF
    assert cm_cmd_remove(ksd) == CMD_success
    assert ksd.lang_ready[LANG_english] == 0


def test_clears_lts_and_ph_pipes() -> None:
    """``lts_pipe`` and ``ph_pipe`` get nulled out."""
    ksd = KsdT()
    ksd.lts_pipe = object()
    ksd.ph_pipe = object()
    cm_cmd_remove(ksd)
    assert ksd.lts_pipe is None
    assert ksd.ph_pipe is None


def test_writes_kill_task_to_lts_pipe() -> None:
    """A KILL_TASK signal is sent via the pipe-write callback."""
    ksd = KsdT()
    fake_pipe = object()
    ksd.lts_pipe = fake_pipe
    writes: list[tuple[object, int]] = []
    cm_cmd_remove(
        ksd,
        lts_pipe_write=lambda pipe, phone: writes.append((pipe, phone)),
    )
    assert writes == [(fake_pipe, KILL_TASK)]


def test_signal_uses_pre_clear_pipe_handle() -> None:
    """The signal is dispatched to the original pipe before nulling."""
    ksd = KsdT()
    original_pipe = object()
    ksd.lts_pipe = original_pipe
    received_pipes: list[object] = []
    cm_cmd_remove(
        ksd,
        lts_pipe_write=lambda pipe, _phone: received_pipes.append(pipe),
    )
    assert received_pipes == [original_pipe]
    assert ksd.lts_pipe is None


def test_returns_success_unconditionally() -> None:
    """No error path; always CMD_success."""
    assert cm_cmd_remove(KsdT()) == CMD_success
