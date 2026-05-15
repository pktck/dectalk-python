"""Bit-parity tests for :func:`dectalk.api.error_state.TextToSpeechGetLastError`."""

from __future__ import annotations

from dataclasses import dataclass

from dectalk.api.error_state import TextToSpeechGetLastError


@dataclass
class _StubHandle:
    """Minimal stand-in for an LPTTS_HANDLE_T with a LastError slot."""

    LastError: int = 0


def test_returns_zero_on_a_fresh_handle() -> None:
    assert TextToSpeechGetLastError(_StubHandle()) == 0


def test_returns_handle_value() -> None:
    assert TextToSpeechGetLastError(_StubHandle(LastError=5)) == 5


def test_returns_arbitrary_unsigned() -> None:
    assert TextToSpeechGetLastError(_StubHandle(LastError=0xDEADBEEF)) == 0xDEADBEEF
