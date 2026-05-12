"""Audio-device state codes from audiodef.h.

Translated from ``src/dapi/src/include/audiodef.h``. The four
audio-device states the audio I/O thread can be in. The C source
declares them as plain ``#define`` constants since the field is
shared with the Windows messaging API on the original platform.

The Windows ``WM_USER + N`` message IDs in audiodef.h are not
ported — they apply only to the Win32 build's message-pump and
the Python port doesn't use a message loop.
"""

from __future__ import annotations

from typing import Final

AUDIO_DEVICE_INACTIVE: Final[int] = 0
"""Audio device is closed / not in use."""

AUDIO_DEVICE_STARTING_UP: Final[int] = 1
"""Audio device is being initialised."""

AUDIO_DEVICE_ACTIVE: Final[int] = 2
"""Audio device is open and actively playing samples."""

AUDIO_DEVICE_SHUTTING_DOWN: Final[int] = 3
"""Audio device is draining its queue prior to close."""

__all__ = [
    "AUDIO_DEVICE_ACTIVE",
    "AUDIO_DEVICE_INACTIVE",
    "AUDIO_DEVICE_SHUTTING_DOWN",
    "AUDIO_DEVICE_STARTING_UP",
]
