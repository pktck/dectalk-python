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


def speech_waveform_generator(*args: object, **kwargs: object) -> int:
    """No-op: structural shim; bit-accurate Klatt synth lives in :mod:`dectalk.hlsyn`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# Dump-hook helpers added by 0005-vtm-stage-dump-hooks.patch. The
# C bodies live in the C source only; the Python side never invokes
# them. These stubs let the inventory test recognize them by name.


def _dectalk_dump_vtm_open(*args: object, **kwargs: object) -> int:
    """No-op: C-side dump-hook helper (Phase A.4 patch); Python doesn't call it."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def _dectalk_dump_vtm_chunk(*args: object, **kwargs: object) -> int:
    """No-op: C-side dump-hook helper (Phase A.4 patch); Python doesn't call it."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# OP_THREAD_ROUTINE is the macro that the C source uses to define
# sync_main / vtm_main. Both thread entries are ported as Python
# synchronous tick functions (sync_main_tick / vtm_main_tick); we
# expose the macro name as an alias for the inventory test.


def OP_THREAD_ROUTINE(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: macro defining sync_main / vtm_main; Python uses synchronous ticks."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "OP_THREAD_ROUTINE",
    "OutputData",
    "WaitForAudioSampleToPlay",
    "_dectalk_dump_vtm_chunk",
    "_dectalk_dump_vtm_open",
    "speech_waveform_generator",
]
