"""TTS feature-bit flags from ttsfeat.h.

Translated from ``src/dapi/src/api/ttsfeat.h``. Each ``TTS_FEATS_*``
constant is a single-bit flag the application uses to query (or
declare) optional TTS-engine capabilities through the public
DECtalk API.

These flags are checked by ``TextToSpeechGetCaps`` and friends —
applications OR together the features they require and the engine
returns the subset it supports.
"""

from __future__ import annotations

from typing import Final

TTS_FEATS_MULTILANG: Final[int] = 0x00000001
"""Engine supports multiple languages (US, UK, German, Spanish, French, …)."""

TTS_FEATS_TYPINGMODE: Final[int] = 0x00000002
"""Engine supports typing mode (per-character speech as the user types)."""

TTS_FEATS_FASTTALK: Final[int] = 0x00000004
"""Engine supports the "fast talk" mode (high-speed playback)."""

TTS_FEATS_HIGHTLIGHTING: Final[int] = 0x00000008
"""Engine supports word-level highlighting callbacks.

The spelling (``HIGHTLIGHTING``) preserves the C header's typo so
grep'ing the C source still locates the constant.
"""

TTS_FEATS_MENUTALK: Final[int] = 0x00000010
"""Engine supports the "menu talk" mode (read GUI menu items aloud)."""


__all__ = [
    "TTS_FEATS_FASTTALK",
    "TTS_FEATS_HIGHTLIGHTING",
    "TTS_FEATS_MENUTALK",
    "TTS_FEATS_MULTILANG",
    "TTS_FEATS_TYPINGMODE",
]
