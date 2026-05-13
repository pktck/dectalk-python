"""SAPI / transport notification structs from tts.h.

Translated from ``src/dapi/src/api/tts.h`` lines 442-471.

Three small notification structs the engine sends to a host
application via its registered notification sink:

- :class:`VisualData` — per-phoneme animation event the host can
  use to drive a viseme animation (timestamp, phoneme code,
  duration, hints).
- :class:`MarkData` — bookmark event delivered when the engine
  reaches a SAPI bookmark marker in the input stream.
- :class:`SinkData` — wraps a sink-callback context with a
  timestamp and two raw data words.

All field types are kept as ``int`` (the QWORD / DWORD originals
are 64- / 32-bit unsigned integers in C) so Python int arithmetic
matches the C wraparound when needed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VisualData:
    """Per-phoneme visual / animation event.

    Faithful translation of:

    .. code-block:: c

        typedef struct VISUAL_DATA_STRUCT {
            QWORD qTimeStamp;
            DWORD dwPhoneme;
            DWORD dwNextPhoneme;
            DWORD dwDuration;
            DWORD dwHints;
            char  cEnginePhoneme;
            char  cNextEnginePhoneme;
        } VISUAL_DATA;

    Attributes:
        qTimeStamp: 64-bit timestamp in 100-ns units.
        dwPhoneme: Current phoneme code (DECtalk-internal, not ASCII).
        dwNextPhoneme: Lookahead phoneme code.
        dwDuration: Phoneme duration in ms.
        dwHints: Bitmask of viseme / animation hints.
        cEnginePhoneme: Engine-side phoneme character (1-byte ASCKY).
        cNextEnginePhoneme: Next engine phoneme character.
    """

    qTimeStamp: int = 0  # noqa: N815
    dwPhoneme: int = 0  # noqa: N815
    dwNextPhoneme: int = 0  # noqa: N815
    dwDuration: int = 0  # noqa: N815
    dwHints: int = 0  # noqa: N815
    cEnginePhoneme: int = 0  # noqa: N815
    cNextEnginePhoneme: int = 0  # noqa: N815


@dataclass(slots=True)
class MarkData:
    """Bookmark event the engine emits when it reaches a SAPI marker.

    Attributes:
        qTimeStamp: 64-bit timestamp in 100-ns units.
        dwMarkValue: Caller-supplied marker integer (or SAPI type-tagged).
        dwMarkType: SAPI mark-type discriminator (bookmark / word-pos /
            sentence / etc.).
    """

    qTimeStamp: int = 0  # noqa: N815
    dwMarkValue: int = 0  # noqa: N815
    dwMarkType: int = 0  # noqa: N815


@dataclass(slots=True)
class SinkData:
    """Notification-sink callback context.

    Wraps a sink-callback pointer with timestamp + two raw data words
    the SAPI transport layer copies between threads.

    Attributes:
        qwTime: 64-bit timestamp.
        pvNotifySink: Pointer to the registered notify / bufnotify sink.
        dwData1: First raw 32-bit data word.
        dwData2: Second raw 32-bit data word.
    """

    qwTime: int = 0  # noqa: N815
    pvNotifySink: object | None = None  # noqa: N815
    dwData1: int = 0  # noqa: N815
    dwData2: int = 0  # noqa: N815


__all__ = ["MarkData", "SinkData", "VisualData"]
