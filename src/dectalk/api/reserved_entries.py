"""Reserved-no-op public entry stubs from ``api/ttsapi.c``.

The DECtalk public C API exposes a small set of ``TextToSpeechReservedN``
entry points that the C source ships as future-feature placeholders -- each
one is a fixed-return-value stub. Python's port surfaces them under the
same C names so callers transitioning from the C library see no symbol
gaps; each returns ``MMSYSERR_NOERROR`` (0) just like the C version.

Reserved entries inventoried:

- :func:`TextToSpeechReserved1` -- reserved no-op
- :func:`TextToSpeechReserved2` -- reserved no-op
- :func:`TextToSpeechReserved3` -- reserved no-op
- :func:`TextToSpeechReserved5` -- reserved no-op
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


def TextToSpeechReserved1(*args: object, **kwargs: object) -> int:  # noqa: N802
    """C-source signature placeholder; always returns ``MMSYSERR_NOERROR``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechReserved2(*args: object, **kwargs: object) -> int:  # noqa: N802
    """C-source signature placeholder; always returns ``MMSYSERR_NOERROR``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechReserved3(*args: object, **kwargs: object) -> int:  # noqa: N802
    """C-source signature placeholder; always returns ``MMSYSERR_NOERROR``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechReserved5(*args: object, **kwargs: object) -> int:  # noqa: N802
    """C-source signature placeholder; always returns ``MMSYSERR_NOERROR``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "TextToSpeechReserved1",
    "TextToSpeechReserved2",
    "TextToSpeechReserved3",
    "TextToSpeechReserved5",
]
