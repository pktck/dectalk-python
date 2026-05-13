"""Verify cm_pars_icommand matches cm_pars.c."""

from __future__ import annotations

from dectalk.cmd.cm_pars_icommand import cm_pars_icommand
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.icomm_struct import IComm


def _with_slot_content(slot_index: int, content: bytes) -> CmdT:
    """Build a CmdT with ``content`` in setv[slot_index]."""
    state = CmdT()
    # setv already has 10 IComm entries; just write the slot.
    state.setv[slot_index] = IComm(cmd=content, seen=0)
    state.cmd_number = slot_index
    state.cmd_count = 0
    state.insertflag = 1  # Active replay.
    return state


def test_returns_first_byte_and_advances() -> None:
    """First call returns the first byte and advances cmd_count to 1."""
    state = _with_slot_content(2, b"abc\x00")
    result = cm_pars_icommand(state)
    assert result == ord("a")
    assert state.cmd_count == 1
    assert state.setv[2].seen == 1  # Incremented on first call.


def test_consecutive_calls_walk_buffer() -> None:
    """Successive calls return the buffer's bytes in order."""
    state = _with_slot_content(0, b"hi\x00")
    assert cm_pars_icommand(state) == ord("h")
    # seen was incremented once; further calls in same replay don't bump it.
    assert state.setv[0].seen == 1
    assert cm_pars_icommand(state) == ord("i")
    assert state.setv[0].seen == 1  # Still 1.


def test_nul_terminator_ends_replay() -> None:
    """Hitting NUL returns 1, clears insertflag, and resets seen."""
    state = _with_slot_content(3, b"x\x00")
    cm_pars_icommand(state)  # 'x'
    result = cm_pars_icommand(state)  # NUL → end
    assert result == 1
    assert state.insertflag == 0
    assert state.setv[3].seen == 0


def test_loop_detection_aborts() -> None:
    """When ``seen`` saturates at 10 with cmd_count==0, abort."""
    state = _with_slot_content(5, b"loop\x00")
    state.setv[5].seen = 10  # At limit.
    result = cm_pars_icommand(state)
    assert result == 1
    assert state.insertflag == 0
    assert state.setv[5].seen == 0


def test_seen_bumps_only_on_first_byte_of_replay() -> None:
    """``seen`` only increments when cmd_count == 0."""
    state = _with_slot_content(0, b"xyz\x00")
    cm_pars_icommand(state)  # cmd_count: 0→1, seen 0→1
    assert state.setv[0].seen == 1
    cm_pars_icommand(state)  # cmd_count 1→2, seen unchanged
    assert state.setv[0].seen == 1
    cm_pars_icommand(state)  # cmd_count 2→3, seen unchanged
    assert state.setv[0].seen == 1


def test_full_replay_then_restart_increments_seen() -> None:
    """Re-running the same slot after end bumps seen again."""
    state = _with_slot_content(1, b"a\x00")
    cm_pars_icommand(state)  # 'a', seen 0→1
    cm_pars_icommand(state)  # NUL → seen reset to 0
    # New replay: cmd_count reset by caller, seen starts at 0 again.
    state.cmd_count = 0
    cm_pars_icommand(state)  # 'a', seen 0→1
    assert state.setv[1].seen == 1


def test_empty_buffer_immediately_ends() -> None:
    """An empty cmd buffer ends replay on the first call."""
    state = _with_slot_content(7, b"")
    result = cm_pars_icommand(state)
    assert result == 1
    assert state.insertflag == 0
