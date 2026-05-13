"""Verify send_index / start_flush / reset_spc match kernel/services.c.

All three C bodies are commented out on the Linux build, so the Python
ports are no-ops. The tests assert that each function is callable, that
it returns ``None``, and that argument objects are not mutated.
"""

from __future__ import annotations

from dectalk.kernel.spc_stubs import reset_spc, send_index, start_flush


def test_send_index_returns_none_on_linux() -> None:
    """``send_index`` is a no-op — body is commented out in services.c."""
    assert send_index(0, 0) is None


def test_send_index_accepts_any_inputs() -> None:
    """Linux no-op accepts the full ``int`` range without raising."""
    assert send_index(1, 12345) is None
    assert send_index(-1, -42) is None
    assert send_index(0xFF, 0) is None


def test_start_flush_returns_none() -> None:
    """``start_flush`` is a no-op regardless of ``serial_mode``."""
    assert start_flush(0) is None
    assert start_flush(1) is None


def test_reset_spc_returns_none() -> None:
    """``reset_spc`` is the ``NOT IMPLEMENTED`` stub — no-op."""
    assert reset_spc() is None


def test_repeated_calls_are_idempotent() -> None:
    """Calling each stub repeatedly stays a no-op."""
    for _ in range(3):
        assert send_index(0, 0) is None
        assert start_flush(0) is None
        assert reset_spc() is None
