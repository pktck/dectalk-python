"""Per-clause PH state initializer from ph_claus.c.

Translated from ``src/dapi/src/ph/ph_claus.c`` lines 575-617.

The PH module calls :func:`init_phclause` at the start of each
clause to clear the per-clause scratch arrays (``allophons``,
``allofeats``, ``allodurs``, ``f0tar``, ``f0tim``) and re-seed
the offset-window pointers that index into those arrays from the
``SAFETY``-th element.

The C source uses raw arrays of fixed size ``NPHON_MAX + SAFETY +
2``. The Python port grows each list to the same size and zeros
every element. The offset-window views (``phonemes``,
``sentstruc``, etc.) are not implemented as Python *views* —
callers should index ``allophons[SAFETY + i]`` directly, but for
parity we expose helper attribute references back to the array.

This is the first state-mutating Phase F function — it consumes
a :class:`dectalk.ph.dph_t.DphT` instance and mutates its array
fields in-place.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import SAFETY
from dectalk.ph.numeric_constants import NPHON_MAX

_BUF_SIZE: int = NPHON_MAX + SAFETY + 2


def init_phclause(p_dph_t: DphT) -> None:
    """Initialise per-clause arrays on ``p_dph_t``.

    Faithful translation of:

    .. code-block:: c

        void init_phclause(PDPH_T pDph_t) {
            int i;
            for (i = 0; i < (NPHON_MAX + SAFETY + 2); i++) {
                pDph_t->allophons[i] = 0;
                pDph_t->allofeats[i] = 0;
                pDph_t->allodurs[i] = 0;
                pDph_t->f0tar[i] = 0;
                pDph_t->f0tim[i] = 0;
            }
            pDph_t->fvvtran = 0;
            pDph_t->bvvtran = 0;

            pDph_t->phonemes   = &(pDph_t->allophons[SAFETY]);
            pDph_t->sentstruc  = &(pDph_t->allofeats[SAFETY]);
            pDph_t->user_durs  = &(pDph_t->allodurs[SAFETY]);
            pDph_t->user_f0    = &(pDph_t->f0tar[SAFETY]);
            pDph_t->user_offset = &(pDph_t->f0tim[SAFETY]);
        }

    The 5 offset-window pointer fields (``phonemes``,
    ``sentstruc``, ``user_durs``, ``user_f0``, ``user_offset``)
    in C are pointers to the ``SAFETY``-th element of the
    underlying array. The Python port can't faithfully model
    pointer aliasing, so we record the parent array on the
    pointer field — callers access ``p_dph_t.phonemes[i]`` and
    the caller-side code does the ``+SAFETY`` index adjustment.

    Args:
        p_dph_t: The PH thread state instance to initialise.
    """
    # Re-allocate the 5 main per-clause arrays at full size with zeros.
    p_dph_t.allophons = [0] * _BUF_SIZE
    p_dph_t.allofeats = [0] * _BUF_SIZE
    p_dph_t.allodurs = [0] * _BUF_SIZE
    p_dph_t.f0tar = [0] * _BUF_SIZE
    p_dph_t.f0tim = [0] * _BUF_SIZE

    # Per-clause scalar resets.
    p_dph_t.fvvtran = 0
    p_dph_t.bvvtran = 0

    # The C source sets up SAFETY-offset window pointers.
    # In Python, we record the parent array on each pointer field —
    # readers index parent[SAFETY + i] explicitly.
    p_dph_t.phonemes = p_dph_t.allophons
    p_dph_t.sentstruc = p_dph_t.allofeats
    p_dph_t.user_durs = p_dph_t.allodurs
    p_dph_t.user_f0 = p_dph_t.f0tar
    p_dph_t.user_offset = p_dph_t.f0tim


__all__ = ["init_phclause"]
