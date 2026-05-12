"""Verify the DtpcCommand dataclass."""

from __future__ import annotations

from dectalk.cmd.command_table import DtpcCommand


def test_default_construction() -> None:
    """DtpcCommand defaults to empty / None."""
    cmd = DtpcCommand()
    assert cmd.c_name == b""
    assert cmd.c_format == b""
    assert cmd.n_params == 0
    assert cmd.esc_value == 0
    assert cmd.c_routine is None


def test_with_handler() -> None:
    """A command entry can carry a handler callable."""

    def fake_handler(_handle: object) -> int:
        return 0

    cmd = DtpcCommand(
        c_name=b"rate",
        c_format=b"n",
        n_params=1,
        esc_value=0xFF,
        c_routine=fake_handler,
    )
    assert cmd.c_name == b"rate"
    assert cmd.c_format == b"n"
    assert cmd.n_params == 1
    assert cmd.esc_value == 0xFF
    assert cmd.c_routine is fake_handler
    assert cmd.c_routine is not None
    assert cmd.c_routine(None) == 0


def test_uses_slots() -> None:
    """DtpcCommand uses slots=True."""
    cmd = DtpcCommand()
    assert not hasattr(cmd, "__dict__")
