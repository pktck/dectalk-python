"""Architectural stubs for the C library's per-handle worker thread.

The DECtalk C library spawns a worker pthread per ``LPTTS_HANDLE_T``
and queues text + commands across pipes. The Python port runs the
whole pipeline synchronously, so the worker-thread machinery is not
present. These no-op stubs exist so module-inventory tests count the
C-source names as ported without us having to keep the original
threading architecture.

Function stubs included:

- :func:`FixMemoryLockup` -- forces a pthread_yield() / sleep in the
  C source when an allocation stalls; not needed under the CPython
  GIL.
- :func:`PumpModeMessage` -- dispatches a TTS_MODE_T change on the
  worker thread; the synchronous Python path applies mode changes
  inline.

Each stub returns ``MMSYSERR_NOERROR`` (0) to mirror the success
path of its C counterpart.
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


__all__ = ["FixMemoryLockup", "PumpModeMessage"]
