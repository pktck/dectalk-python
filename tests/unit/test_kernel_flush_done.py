"""Verify flush_done matches kernel/services.c."""

from __future__ import annotations

from dectalk.kernel.flush_done import flush_done
from dectalk.kernel.ksd_t import KsdT


def test_clears_cmd_flush() -> None:
    """``cmd_flush`` is cleared to 0 (false)."""
    state = KsdT()
    state.cmd_flush = 1
    flush_done(state)
    assert state.cmd_flush == 0


def test_zeros_spc_sync_value() -> None:
    """``spc_sync.value`` is reset to 0."""
    state = KsdT()
    state.spc_sync.value = 42
    flush_done(state)
    assert state.spc_sync.value == 0


def test_idempotent_when_already_clear() -> None:
    """Calling on a clear state is a no-op."""
    state = KsdT()
    flush_done(state)
    assert state.cmd_flush == 0
    assert state.spc_sync.value == 0


def test_other_fields_untouched() -> None:
    """Fields unrelated to flushing aren't disturbed."""
    state = KsdT()
    state.lang_curr = 5
    state.ascky_size = 256
    state.cmd_flush = 1
    flush_done(state)
    assert state.lang_curr == 5
    assert state.ascky_size == 256
