"""``raise_last_stress`` helper from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1891-1903.

Walks backward from ``msym - 1`` looking for the most recent
primary-stress (``S1``) marker in the ``symbols[]`` array. When
found, promotes it to emphatic-stress (``SEMPH``). Used during
intonation sorting to elevate a re-stressed word's prior stress.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.phoneme_codes import S1, SEMPH
from dectalk.ph.dph_t import DphT


def raise_last_stress(p_dph_t: DphT, msym: int) -> None:
    """Promote the most recent ``S1`` before ``msym`` to ``SEMPH``.

    Faithful translation of:

    .. code-block:: c

        static void raise_last_stress(PDPH_T pDph_t, short msym) {
            short m;
            for (m = msym - 1; m > 0; m--) {
                if ((pDph_t->symbols[m] & PVALUE) == S1) {
                    pDph_t->symbols[m] = SEMPH;
                    return;
                }
            }
        }

    The walk explicitly skips ``m = 0`` (the C source's
    ``m > 0`` guard), so symbol index 0 cannot be the upgrade
    target.

    Args:
        p_dph_t: PH thread state.
        msym: Starting index — the function walks backward from
            ``msym - 1``.
    """
    symbols = p_dph_t.symbols
    for m in range(msym - 1, 0, -1):
        if m >= len(symbols):
            continue
        if (symbols[m] & PVALUE) == S1:
            symbols[m] = SEMPH
            return


__all__ = ["raise_last_stress"]
