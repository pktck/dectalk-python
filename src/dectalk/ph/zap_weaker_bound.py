"""``zap_weaker_bound`` helper from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1920-1937.

Compares two boundary markers at ``msym1`` and ``msym2``. The
weaker (smaller-valued) boundary is deleted; if ``msym1 < msym2``,
``msym1`` first absorbs ``msym2``'s strength then gets deleted
(unless it's a ``HYPHEN``, which is preserved).

Used during intonation sorting to merge adjacent boundary markers
into a single stronger one.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import HYPHEN
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.delete_symbol import delete_symbol
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT


def zap_weaker_bound(
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
    msym1: int,
    msym2: int,
) -> None:
    """Zap the weaker of two boundary markers and promote the first.

    Faithful translation of:

    .. code-block:: c

        static void zap_weaker_bound(LPTTS_HANDLE_T phTTS,
                                     short msym1, short msym2) {
            if (pDph_t->symbols[msym1] < pDph_t->symbols[msym2]) {
                pDph_t->symbols[msym1] = pDph_t->symbols[msym2];
                if (pDph_t->symbols[msym1] != HYPHEN)
                    delete_symbol(phTTS, msym1);
                return;
            }
            if (pDph_t->symbols[msym2] != HYPHEN)
                delete_symbol(phTTS, msym2);
        }

    Args:
        p_ksd_t: Kernel shared-data struct (for SPC chain anchor).
        p_dph_t: PH thread state.
        pst_phsettar: Per-clause settar struct (``did_del`` updated
            by :func:`delete_symbol`).
        msym1: Index of the first boundary marker.
        msym2: Index of the second boundary marker.
    """
    symbols = p_dph_t.symbols
    if msym1 < 0 or msym2 < 0 or msym1 >= len(symbols) or msym2 >= len(symbols):
        return

    if symbols[msym1] < symbols[msym2]:
        # msym1 is weaker — promote it then delete (unless HYPHEN).
        symbols[msym1] = symbols[msym2]
        if symbols[msym1] != HYPHEN:
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, msym1)
        return
    # msym2 is weaker (or equal) — delete it (unless HYPHEN).
    if symbols[msym2] != HYPHEN:
        delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, msym2)


__all__ = ["zap_weaker_bound"]
