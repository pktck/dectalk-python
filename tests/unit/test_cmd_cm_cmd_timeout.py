"""Verify cm_cmd_timeout matches cm_copt.c."""

from __future__ import annotations

from dectalk.cmd.cm_cmd_timeout import cm_cmd_timeout
from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.kernel.ksd_t import KsdT


def test_default_value_resets_timeout_to_zero() -> None:
    """When defaults[0]==True, params[0] is overwritten to 0."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.params = [99]
    cmd.defaults = [1]  # TRUE — default invoked.
    assert cm_cmd_timeout(ksd, cmd) == CMD_success
    assert cmd.params[0] == 0
    assert cmd.timeout == 0
    assert ksd.input_timeout == 0


def test_explicit_value_copied_to_both_fields() -> None:
    """An explicit param value flows into both timeout fields."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.params = [42]
    cmd.defaults = [0]  # FALSE — explicit value provided.
    assert cm_cmd_timeout(ksd, cmd) == CMD_success
    assert cmd.timeout == 42
    assert ksd.input_timeout == 42


def test_empty_params_treats_as_zero() -> None:
    """An empty params list is treated as 0 — defensive."""
    ksd = KsdT()
    cmd = CmdT()
    assert cm_cmd_timeout(ksd, cmd) == CMD_success
    assert cmd.timeout == 0
    assert ksd.input_timeout == 0


def test_returns_success_unconditionally() -> None:
    """The C source has no error path; always CMD_success."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.params = [-99999]  # Even pathological values succeed.
    cmd.defaults = [0]
    assert cm_cmd_timeout(ksd, cmd) == CMD_success
