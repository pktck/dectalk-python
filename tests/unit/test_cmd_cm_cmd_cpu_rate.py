"""Verify cm_cmd_cpu_rate matches cm_copt.c (Linux no-op build)."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_cpu_rate import cm_cmd_cpu_rate
from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def test_returns_success_on_linux_unconditionally() -> None:
    """Linux build is a no-op — always CMD_success."""
    cmd = CmdT()
    assert cm_cmd_cpu_rate(cmd) == CMD_success


def test_returns_success_with_any_params() -> None:
    """Inputs that would fail on MSDOS are still success on Linux."""
    cmd = CmdT()
    cmd.params = [99]  # > 25; would be CMD_bad_value on MSDOS.
    cmd.defaults = [0]
    assert cm_cmd_cpu_rate(cmd) == CMD_success


def test_does_not_mutate_cmd_state() -> None:
    """No-op build doesn't touch any CmdT fields."""
    cmd = CmdT()
    cmd.params = [5]
    cmd.defaults = [0]
    cm_cmd_cpu_rate(cmd)
    assert cmd.params == [5]
    assert cmd.defaults == [0]
