"""Verify cm_cmd_setv matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_setv import cm_cmd_setv
from dectalk.cmd.cmd_states import CMD_bad_value, CMD_success
from dectalk.cmd.cmd_t import CmdT


def _with_slot(slot: int) -> CmdT:
    """Build a CmdT carrying ``slot`` in params[0]."""
    state = CmdT()
    state.params = [slot]
    return state


def test_valid_slot_zero() -> None:
    """Slot 0 is the lowest valid setv index."""
    cmd = _with_slot(0)
    assert cm_cmd_setv(cmd) == CMD_success
    assert cmd.cmd_number == 0
    assert cmd.insertflag == 1
    assert cmd.cmd_count == 0


def test_valid_slot_nine() -> None:
    """Slot 9 is the highest valid setv index."""
    cmd = _with_slot(9)
    assert cm_cmd_setv(cmd) == CMD_success
    assert cmd.cmd_number == 9


def test_slot_out_of_range_high() -> None:
    """Slot 10 is out of range — returns CMD_bad_value."""
    cmd = _with_slot(10)
    assert cm_cmd_setv(cmd) == CMD_bad_value
    assert cmd.cmd_number == 0  # Unchanged.
    assert cmd.insertflag == 0  # Unchanged.


def test_slot_out_of_range_negative() -> None:
    """Negative slot is out of range — returns CMD_bad_value."""
    cmd = _with_slot(-1)
    assert cm_cmd_setv(cmd) == CMD_bad_value


def test_cmd_count_reset_to_zero() -> None:
    """``cmd_count`` is reset to 0 on success."""
    cmd = _with_slot(5)
    cmd.cmd_count = 99  # Non-zero starting value.
    cm_cmd_setv(cmd)
    assert cmd.cmd_count == 0


def test_insertflag_set_to_one() -> None:
    """``insertflag`` is set to 1 (non-VOCAL build)."""
    cmd = _with_slot(3)
    cm_cmd_setv(cmd)
    assert cmd.insertflag == 1


def test_empty_params_returns_bad_value() -> None:
    """An empty params list is treated as slot=-1 (bad value)."""
    cmd = CmdT()
    assert cm_cmd_setv(cmd) == CMD_bad_value
