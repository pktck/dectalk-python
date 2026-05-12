"""LIMIT and IQUEUE structs from viphdefs.h.

Translated from ``src/dapi/src/vtm/viphdefs.h``. Two small structs
the PH module uses for bookkeeping:

- :class:`Limit` — speaker-def limit-table entry holding the
  min/max range for one Klatt parameter.
- :class:`IndexEvent` — one entry in the index-event queue
  (``pDph_t->index_queue[NIQUEUE]``). Recorded when the input
  text contains an ``INDEX`` or ``INDEX_REPLY`` marker.

- :data:`NIQUEUE` — capacity of the index event queue (250).
- :data:`GUARD` — guard-band threshold (``25`` frames) used by
  the WBOUND → COMMA promotion logic when the pipeline approaches
  capacity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(slots=True)
class Limit:
    """Speaker-def limit entry: ``(min, max)`` for one Klatt parameter.

    Attributes:
        l_min: Minimum allowed value.
        l_max: Maximum allowed value.
    """

    l_min: int = 0
    l_max: int = 0


@dataclass(slots=True)
class IndexEvent:
    """One entry in the PH module's index-event queue.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            short i_offset;   // Offset into "symbols"
            short i_type;     // Type: INDEX or INDEX_REPLY
            short i_value;    // Value of the index
        } IQUEUE;

    Attributes:
        i_offset: Symbol-stream offset where the index marker was hit.
        i_type: Index type — typically :data:`~dectalk.include.cmd_codes.INDEX`
            or :data:`~dectalk.include.cmd_codes.INDEX_REPLY`.
        i_value: The user-supplied index value.
    """

    i_offset: int = 0
    i_type: int = 0
    i_value: int = 0


NIQUEUE: Final[int] = 250
"""Capacity of the per-PH index-event queue."""

GUARD: Final[int] = 25
"""Guard-band threshold (frames). When pipeline depth exceeds this near
``NLPIPE`` capacity, the PH module promotes the next WBOUND into a
COMMA to insert a pause."""


__all__ = ["GUARD", "NIQUEUE", "IndexEvent", "Limit"]
