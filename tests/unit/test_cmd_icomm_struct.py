"""Verify the IComm dataclass models cm_data.h's ICOMM_T."""

from __future__ import annotations

from dectalk.cmd.icomm_struct import IComm


def test_default_construction() -> None:
    """IComm defaults to (b'', 0)."""
    ic = IComm()
    assert ic.cmd == b""
    assert ic.seen == 0


def test_construction_kwargs() -> None:
    """Fields are settable at construction."""
    ic = IComm(cmd=b":rate 200", seen=1)
    assert ic.cmd == b":rate 200"
    assert ic.seen == 1


def test_loop_detect_increment() -> None:
    """`seen` is bumped to track parser loops."""
    ic = IComm(cmd=b":dv ap 110")
    ic.seen += 1
    assert ic.seen == 1
    ic.seen += 1
    assert ic.seen == 2


def test_uses_slots() -> None:
    """IComm uses slots=True."""
    ic = IComm()
    assert not hasattr(ic, "__dict__")
