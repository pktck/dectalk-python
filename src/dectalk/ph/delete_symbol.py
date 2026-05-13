"""``delete_symbol`` helper from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1952-1986.

Deletes the symbol at index ``msym`` from ``symbols[]`` (and the
parallel ``user_durs[]`` / ``user_f0[]`` arrays) by shifting all
later elements down by one position. Decrements ``nsymbtot``,
sets the ``did_del`` flag on the settar state, and re-anchors the
SPC packet chain via :func:`adjust_index`.
"""

from __future__ import annotations

from dectalk.kernel.adjust_index import adjust_index
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT


def delete_symbol(
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
    msym: int,
) -> None:
    """Delete ``symbols[msym]`` and shift later symbols down.

    Faithful translation of:

    .. code-block:: c

        static void delete_symbol(LPTTS_HANDLE_T phTTS, short msym) {
            short m;
            pDph_t->nsymbtot--;
            pDphsettar->did_del = 1;
            for (m = msym; m < pDph_t->nsymbtot; m++) {
                pDph_t->symbols[m]   = pDph_t->symbols[m + 1];
                pDph_t->user_durs[m] = pDph_t->user_durs[m + 1];
                pDph_t->user_f0[m]   = pDph_t->user_f0[m + 1];
            }
            adjust_index(pKsd_t, msym + 1, -1, 1);
        }

    Args:
        p_ksd_t: Kernel shared-data struct (for the SPC index chain).
        p_dph_t: PH thread state to mutate.
        pst_phsettar: Per-clause settar struct (``did_del`` is set).
        msym: Index of the symbol to delete.
    """
    p_dph_t.nsymbtot -= 1
    pst_phsettar.did_del = 1

    symbols = p_dph_t.symbols
    user_durs = p_dph_t.user_durs
    user_f0 = p_dph_t.user_f0
    for m in range(msym, p_dph_t.nsymbtot):
        if m + 1 < len(symbols):
            symbols[m] = symbols[m + 1]
        if user_durs is not None and m + 1 < len(user_durs):
            user_durs[m] = user_durs[m + 1]
        if user_f0 is not None and m + 1 < len(user_f0):
            user_f0[m] = user_f0[m + 1]

    # Re-anchor the SPC index chain so any pending packets following
    # this position drop their allo index by 1.
    adjust_index(p_ksd_t.spc_pkt_save, msym + 1, -1, 1)


__all__ = ["delete_symbol"]
