"""ASCKY-to-pipe code conversion struct from cm_data.h.

Translated from ``src/dapi/src/cmd/cm_data.h``. ``ASCKY_TAB`` pairs
an ASCKY graphic byte with its corresponding phonemic code in the
pipe protocol.

Note: The phoneme-mapping payload of the ascky_table is already
ported as a tuple-of-tuples in :mod:`dectalk.lts.math_mode`
(:data:`~dectalk.lts.math_mode.ascky_tab`). This module just exposes
the per-row struct shape for callers that need to index a single
entry as a named record.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AsckyTab:
    """One ASCKY-to-phoneme row.

    Faithful translation of:

    .. code-block:: c

        typedef struct ascky_table {
            char p_graph;        // Graphic code
            char p_phone_phone;  // Phonemic code
        } ASCKY_TAB;

    The C source's field name ``p_phone_phone`` is reproduced
    verbatim (the doubled "phone" is a historical artefact, not a
    typo on our side).

    Attributes:
        p_graph: Graphic-code byte (e.g. ``b'e'`` for ASCKY ``e``).
        p_phone_phone: Phonemic-code byte the parser emits.
    """

    p_graph: int = 0
    p_phone_phone: int = 0


__all__ = ["AsckyTab"]
