"""Phoneme-mark structs from ttsapi.h.

Translated from ``src/dapi/src/api/ttsapi.h``. Two parallel structs
the public API uses to package phoneme + duration info in the
TTS_MSG_INDEX_MARK callback stream:

- :class:`PhonemeMark` — original 8-bit phoneme codes
  (``UCHAR``/``unsigned char``).
- :class:`PhonemeMark2` — extended 16-bit phoneme codes
  (``USHORT``/``unsigned short``) added for languages with more
  than 256 distinct phonemes.

Both carry the same ``wDuration`` field (milliseconds). The C
source unions them via ``PHONEME_TAG``; the Python port exposes
them as separate classes since Python's duck-typing makes the
union less useful.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PhonemeMark:
    """8-bit phoneme-mark entry (original PHONEME_MARK struct).

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            unsigned char cThisPhoneme;
            unsigned char cNextPhoneme;
            WORD          wDuration;
        } PHONEME_MARK;

    Attributes:
        c_this_phoneme: Current phoneme code (8-bit).
        c_next_phoneme: Next phoneme code (8-bit), 0 if unknown.
        w_duration: Duration of the current phoneme in milliseconds.
    """

    c_this_phoneme: int = 0
    c_next_phoneme: int = 0
    w_duration: int = 0


@dataclass(slots=True)
class PhonemeMark2:
    """16-bit phoneme-mark entry (extended PHONEME_MARK2 struct).

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            unsigned short cThisPhoneme;
            unsigned short cNextPhoneme;
            WORD           wDuration;
        } PHONEME_MARK2;

    Attributes:
        c_this_phoneme: Current phoneme code (16-bit, font-encoded).
        c_next_phoneme: Next phoneme code (16-bit), 0 if unknown.
        w_duration: Duration of the current phoneme in milliseconds.
    """

    c_this_phoneme: int = 0
    c_next_phoneme: int = 0
    w_duration: int = 0


__all__ = ["PhonemeMark", "PhonemeMark2"]
