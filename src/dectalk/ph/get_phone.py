"""``get_phone`` helper from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` lines 1627-1643.

Safe-bounds accessor over ``pDph_t->allophons``: returns the
phone at ``pointer`` if in range, else :data:`GEN_SIL` (the
silence sentinel). Used throughout the PH module's setar /
timing passes for looking at neighbouring phones.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.utterance_constants import GEN_SIL


def get_phone(p_dph_t: DphT, pointer: int) -> int:
    """Return ``allophons[pointer]`` or :data:`GEN_SIL` out of range.

    Faithful translation of:

    .. code-block:: c

        static short get_phone(PDPH_T pDph_t, short pointer) {
            if (pointer >= 0 && pointer < pDph_t->nallotot)
                return pDph_t->allophons[pointer];
            else
                return GEN_SIL;
        }

    Args:
        p_dph_t: PH thread state.
        pointer: Index into ``allophons``.

    Returns:
        The phone code at ``pointer`` if ``0 <= pointer < nallotot``;
        otherwise :data:`GEN_SIL`.
    """
    if 0 <= pointer < p_dph_t.nallotot and pointer < len(p_dph_t.allophons):
        return p_dph_t.allophons[pointer]
    return GEN_SIL


__all__ = ["get_phone"]
