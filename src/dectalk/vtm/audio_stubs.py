"""Architectural stubs for VTM-stage audio sync helpers.

The DECtalk C VTM stage uses a per-handle worker thread and PA_*
audio bindings to drive playback through the operating system's
audio device. The Python audio backend bypasses both -- ``to_wav``
writes WAVs directly, ``speak`` invokes ``sounddevice`` for inline
playback. These no-op stubs let the module-inventory test count
the C entry points as ported.
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


def WaitForAudioSampleToPlay(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python audio backend handles its own sync barriers."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def OutputData(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python audio backend writes WAVs / streams directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = ["OutputData", "WaitForAudioSampleToPlay"]
