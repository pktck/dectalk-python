"""``move_stdangle`` helper from ph_sort2.c.

Translated from ``src/dapi/src/ph/ph_sort2.c`` lines 211-355
(forward-declared in ``ph_sort.c`` at line 195).

Moves a dangling stress symbol further into the current word so it
either replaces a weaker stress, attaches to the next syllabic
segment, or gets dropped at a word boundary. The three rules are:

1. **Emphasis** (``SEMPH``): walk forward to the first ``S1`` in the
   word and promote it to ``SEMPH``; if no ``S1``, do the same for the
   first ``S2``. Either way, delete the dangling marker at ``msym``.
2. **Primary stress** (``S1``): walk forward to the first ``S2`` in
   the word, promote it to ``S1``, delete the dangling marker.
3. **Otherwise / fallthrough**: walk forward until we hit a word
   boundary (delete the symbol just before the boundary), another
   stress marker (replace if weaker, delete the symbol just before
   it), or a syllabic phone (place the stress on the slot just before
   it). Non-stress, non-syllabic symbols are shifted backward one
   slot as the cursor advances, "carrying" the stress forward.

Note: the C source has ``f0dangle = pDph_t->user_durs[msym];`` (sic) —
it reads ``user_durs`` not ``user_f0`` when seeding ``f0dangle``. The
Python port preserves this verbatim for bit-parity.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.phoneme_codes import S1, S2, SEMPH
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.delete_symbol import delete_symbol
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.is_wboundary import is_wboundary
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature


def move_stdangle(  # noqa: PLR0911, PLR0912, PLR0915
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
    msym: int,
) -> None:
    """Move a dangling stress symbol forward to the right slot.

    Faithful translation of:

    .. code-block:: c

        static void move_stdangle(LPTTS_HANDLE_T phTTS, short msym) {
            short m, stdangle, durdangle, f0dangle;
            PDPH_T pDph_t = phTTS->pPHThreadData;

            stdangle  = pDph_t->symbols[msym] & PVALUE;
            durdangle = pDph_t->user_durs[msym];
            f0dangle  = pDph_t->user_durs[msym];   // (sic - reads user_durs)

            /* 1. If emphasis, replace strongest stress in current word */
            if (stdangle == SEMPH) {
                for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                    if (pDph_t->symbols[m] == S1) {
                        pDph_t->symbols[m] = SEMPH;
                        pDph_t->user_durs[m] = durdangle;
                        pDph_t->user_f0[m]   = f0dangle;
                        delete_symbol(phTTS, msym);
                        return;
                    }
                    if (is_wboundary(pDph_t->symbols[m])) break;
                }
                for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                    if (pDph_t->symbols[m] == S2) {
                        pDph_t->symbols[m] = SEMPH;
                        pDph_t->user_durs[m] = durdangle;
                        pDph_t->user_f0[m]   = f0dangle;
                        delete_symbol(phTTS, msym);
                        return;
                    }
                    if (is_wboundary(pDph_t->symbols[m])) break;
                }
            }
            /* 2. If primary, replace first secondary stress in word */
            if (stdangle == S1) {
                for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                    if (pDph_t->symbols[m] == S2) {
                        pDph_t->symbols[m] = S1;
                        pDph_t->user_durs[m] = durdangle;
                        pDph_t->user_f0[m]   = f0dangle;
                        delete_symbol(phTTS, msym);
                        return;
                    }
                    if (is_wboundary(pDph_t->symbols[m])) break;
                }
            }
            /* 3. Attach to first vowel encountered; if a stress mark
             *    appears first, replace it if weaker, then delete. */
            for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                if (is_wboundary(pDph_t->symbols[m])) {
                    delete_symbol(phTTS, (short)(m - 1));
                    return;
                }
                if (((pDph_t->symbols[m] & PVALUE) >= S2)
                 && ((pDph_t->symbols[m] & PVALUE) <= SEMPH)) {
                    if ((pDph_t->symbols[m] & PVALUE) < stdangle) {
                        pDph_t->symbols[m] = stdangle;
                        pDph_t->user_durs[m] = durdangle;
                        pDph_t->user_f0[m]   = f0dangle;
                    }
                    delete_symbol(phTTS, (short)(m - 1));
                    return;
                }
                else if ((phone_feature(pDph_t, pDph_t->symbols[m])
                          & FSYLL) IS_PLUS) {
                    pDph_t->symbols[m - 1]   = stdangle;
                    pDph_t->user_durs[m - 1] = durdangle;
                    pDph_t->user_f0[m - 1]   = f0dangle;
                    return;
                }
                else {
                    pDph_t->symbols[m - 1]   = pDph_t->symbols[m];
                    pDph_t->user_durs[m - 1] = pDph_t->user_durs[m];
                    pDph_t->user_f0[m - 1]   = pDph_t->user_f0[m];
                }
            }
        }

    Args:
        p_ksd_t: Kernel shared-data struct (forwarded to
            :func:`delete_symbol` for SPC chain re-anchoring).
        p_dph_t: PH thread state to mutate.
        pst_phsettar: Per-clause settar struct (its ``did_del`` flag is
            set whenever :func:`delete_symbol` is invoked).
        msym: Index of the dangling stress symbol to move.
    """
    symbols = p_dph_t.symbols
    user_durs = p_dph_t.user_durs
    user_f0 = p_dph_t.user_f0

    if msym < 0 or msym >= len(symbols):
        return

    stdangle = symbols[msym] & PVALUE
    durdangle = user_durs[msym] if user_durs is not None and msym < len(user_durs) else 0
    # NOTE: C source reads user_durs[msym] for both durdangle and f0dangle (sic).
    f0dangle = user_durs[msym] if user_durs is not None and msym < len(user_durs) else 0

    # Rule 1: emphasis — promote first S1 (or fallback to S2) in word.
    if stdangle == SEMPH:
        for m in range(msym + 1, p_dph_t.nsymbtot):
            if m >= len(symbols):
                break
            if symbols[m] == S1:
                symbols[m] = SEMPH
                if user_durs is not None and m < len(user_durs):
                    user_durs[m] = durdangle
                if user_f0 is not None and m < len(user_f0):
                    user_f0[m] = f0dangle
                delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, msym)
                return
            if is_wboundary(symbols[m]):
                break  # No longer current word; give up S1 search.
        for m in range(msym + 1, p_dph_t.nsymbtot):
            if m >= len(symbols):
                break
            if symbols[m] == S2:
                symbols[m] = SEMPH
                if user_durs is not None and m < len(user_durs):
                    user_durs[m] = durdangle
                if user_f0 is not None and m < len(user_f0):
                    user_f0[m] = f0dangle
                delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, msym)
                return
            if is_wboundary(symbols[m]):
                break  # No longer current word; give up S2 search.

    # Rule 2: primary stress — promote first S2 in word to S1.
    if stdangle == S1:
        for m in range(msym + 1, p_dph_t.nsymbtot):
            if m >= len(symbols):
                break
            if symbols[m] == S2:
                symbols[m] = S1
                if user_durs is not None and m < len(user_durs):
                    user_durs[m] = durdangle
                if user_f0 is not None and m < len(user_f0):
                    user_f0[m] = f0dangle
                delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, msym)
                return
            if is_wboundary(symbols[m]):
                break  # No longer current word; give up S2 search.

    # Rule 3: attach to first vowel; use stronger of two stresses if
    # another stress encountered before a vowel.
    for m in range(msym + 1, p_dph_t.nsymbtot):
        if m >= len(symbols):
            break
        if is_wboundary(symbols[m]):
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, m - 1)
            return
        sym_val = symbols[m] & PVALUE
        if S2 <= sym_val <= SEMPH:
            if sym_val < stdangle:
                symbols[m] = stdangle
                if user_durs is not None and m < len(user_durs):
                    user_durs[m] = durdangle
                if user_f0 is not None and m < len(user_f0):
                    user_f0[m] = f0dangle
            delete_symbol(p_ksd_t, p_dph_t, pst_phsettar, m - 1)
            return
        if (phone_feature(symbols[m]) & FSYLL) != 0:
            # Found syllabic — put stress on prior slot.
            symbols[m - 1] = stdangle
            if user_durs is not None and m - 1 < len(user_durs):
                user_durs[m - 1] = durdangle
            if user_f0 is not None and m - 1 < len(user_f0):
                user_f0[m - 1] = f0dangle
            return
        # Non-stress non-syllabic: shift symbol backward one slot.
        symbols[m - 1] = symbols[m]
        if user_durs is not None and m - 1 < len(user_durs) and m < len(user_durs):
            user_durs[m - 1] = user_durs[m]
        if user_f0 is not None and m - 1 < len(user_f0) and m < len(user_f0):
            user_f0[m - 1] = user_f0[m]


__all__ = ["move_stdangle"]
