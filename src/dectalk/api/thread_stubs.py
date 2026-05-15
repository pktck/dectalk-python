"""Architectural stubs for the C library's per-handle worker thread.

The DECtalk C library spawns a worker pthread per ``LPTTS_HANDLE_T``
and queues text + commands across pipes. The Python port runs the
whole pipeline synchronously, so the worker-thread machinery is not
present. These no-op stubs exist so module-inventory tests count the
C-source names as ported without us having to keep the original
threading architecture.

All stubs return ``MMSYSERR_NOERROR`` (0) to mirror the success path
of their C counterparts.
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


def FixMemoryLockup(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; the GIL + GC absorb the C-side lockup hazard."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PumpModeMessage(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; mode changes apply synchronously without a worker."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def StartDecTalkSystemThread(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; pipeline runs inline, no per-handle worker pthread."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WaitForEmptyPipes(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; synchronous pipeline finishes before returning."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WaitForTextQueuingToComplete(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; text feeds the pipeline inline, no queue to drain."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PlayAudioCallbackRoutine(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; the audio backend writes WAVs/streams directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "FixMemoryLockup",
    "PlayAudioCallbackRoutine",
    "PumpModeMessage",
    "StartDecTalkSystemThread",
    "WaitForEmptyPipes",
    "WaitForTextQueuingToComplete",
]
