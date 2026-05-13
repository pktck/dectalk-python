"""``insertphone`` helper from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1846-1876.

Inserts a phoneme code ``fone`` at index ``loc`` in
``pDph_t->symbols[]``, pushing all later entries down by one
position. Also clears the user-prosody (``user_durs`` / ``user_f0``)
slot for the new symbol so leftover values from the prior occupant
don't propagate.

After the shift, re-anchors the SPC index chain via
:func:`adjust_index` (unless the inserted symbol is ``S1`` — the
KSB BATS bug fix preserves S1 markers' index alignment).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1
from dectalk.kernel.adjust_index import adjust_index
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import NPHON_MAX


def insertphone(p_ksd_t: KsdT, p_dph_t: DphT, loc: int, fone: int) -> None:
    """Insert ``fone`` at ``symbols[loc]`` and push later entries down.

    Faithful translation of:

    .. code-block:: c

        static void insertphone(LPTTS_HANDLE_T phTTS, short loc, short fone) {
            short m;
            if (pDph_t->nsymbtot >= NPHON_MAX) return;
            for (m = pDph_t->nsymbtot; m > loc; m--) {
                pDph_t->symbols[m]   = pDph_t->symbols[m - 1];
                pDph_t->user_durs[m] = pDph_t->user_durs[m - 1];
                pDph_t->user_f0[m]   = pDph_t->user_f0[m - 1];
            }
            pDph_t->symbols[loc] = fone;
            pDph_t->user_durs[loc] = 0;
            pDph_t->user_f0[loc] = 0;
            pDph_t->nsymbtot++;
            if (fone != S1)
                adjust_index(pKsd_t, loc + 1, 1, 0);
        }

    Args:
        p_ksd_t: Kernel shared-data struct (for SPC chain).
        p_dph_t: PH thread state to mutate.
        loc: Insertion index.
        fone: Phoneme code to insert.
    """
    if p_dph_t.nsymbtot >= NPHON_MAX:
        return

    symbols = p_dph_t.symbols
    user_durs = p_dph_t.user_durs
    user_f0 = p_dph_t.user_f0

    # Grow buffers to fit nsymbtot+1.
    while len(symbols) <= p_dph_t.nsymbtot:
        symbols.append(0)
    if user_durs is not None:
        while len(user_durs) <= p_dph_t.nsymbtot:
            user_durs.append(0)
    if user_f0 is not None:
        while len(user_f0) <= p_dph_t.nsymbtot:
            user_f0.append(0)

    # Shift later entries down by one.
    for m in range(p_dph_t.nsymbtot, loc, -1):
        symbols[m] = symbols[m - 1]
        if user_durs is not None:
            user_durs[m] = user_durs[m - 1]
        if user_f0 is not None:
            user_f0[m] = user_f0[m - 1]

    symbols[loc] = fone
    if user_durs is not None and 0 <= loc < len(user_durs):
        user_durs[loc] = 0
    if user_f0 is not None and 0 <= loc < len(user_f0):
        user_f0[loc] = 0

    p_dph_t.nsymbtot += 1

    # Re-anchor SPC chain — but skip the adjust for S1 (BATS fix).
    if fone != S1:
        adjust_index(p_ksd_t.spc_pkt_save, loc + 1, 1, 0)


__all__ = ["insertphone"]
