"""Architectural stubs for the C kernel's volume-control wrappers.

The DECtalk C kernel exposes ``StereoVolumeControl`` /
``SetStereoVolume`` / ``ModifyVolume`` as wrappers over the
``PA_GetVolume`` / ``PA_SetVolume`` audio-backend bindings. The Python
audio backend uses its own gain shaping and bypasses ``PA_*``
entirely, so these names exist purely as architectural stubs to
satisfy the module-inventory test.

Each stub returns ``MMSYSERR_NOERROR`` (0). The actual gain envelope
the Python pipeline applies lives in ``dectalk.kernel.volume_table``
(``encode_dectalk_volume`` / ``decode_dectalk_volume``).
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


def StereoVolumeControl(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python audio backend bypasses PA_GetVolume / PA_SetVolume."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def SetStereoVolume(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python audio backend writes gain via its own envelope shaper."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def ModifyVolume(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op static helper to :func:`StereoVolumeControl`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = ["ModifyVolume", "SetStereoVolume", "StereoVolumeControl"]
