"""``make_out_phonol`` helper from ph_aloph2.c.

Translated from ``src/dapi/src/ph/ph_aloph2.c`` lines 1812-1903.

Writes one allophone + feature + user-prosody triple into the PH
output buffers (``allophons`` / ``allofeats`` / ``user_durs`` /
``user_f0``) and bumps ``nallotot``. Used by the allophonic-
substitution pass as it emits the post-substitution phoneme
stream.

The C source pre-calls ``set_index_allo`` to maintain the SPC
index chain anchored on this output slot; this Python port does
the same via the already-ported :func:`set_index_allo`.

Caveat: the C source has a defensive ``if (nallotot > (n + 8))``
check that returns early with a printf complaint. Preserved
verbatim — the threshold of 8 isn't documented but appears to be
a safety margin against runaway substitution.
"""

from __future__ import annotations

from dectalk.kernel.adjust_allo import set_index_allo
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import HAT_F0_SIZES_SPECIFIED
from dectalk.ph.numeric_constants import NPHON_MAX

_ALLO_DEFENSIVE_MARGIN = 8  # nallotot > n + 8 → C source bails out.


def make_out_phonol(
    p_ksd_t: KsdT,
    p_dph_t: DphT,
    n: int,
    curr_outph: int,
    curr_outstruc: int,
    curr_indur: int,
    curr_inf0: int,
) -> None:
    """Append one allophone + feature record to the PH output buffer.

    Faithful translation of the non-MSDOS branch of:

    .. code-block:: c

        static void make_out_phonol(LPTTS_HANDLE_T phTTS, short n,
                                    short curr_outph, U32 curr_outstruc,
                                    short curr_indur, short curr_inf0) {
            set_index_allo(pKsd_t, n, pDph_t->nallotot);
            if (pDph_t->nallotot > (n + 8)) return;
            pDph_t->allophons[pDph_t->nallotot] = curr_outph;
            pDph_t->allofeats[pDph_t->nallotot] = curr_outstruc;
            pDph_t->user_durs[pDph_t->nallotot] = curr_indur;
            if (pDph_t->f0mode != HAT_F0_SIZES_SPECIFIED)
                pDph_t->user_f0[pDph_t->nallotot] = curr_inf0;
            if (pDph_t->nallotot < NPHON_MAX) pDph_t->nallotot++;
        }

    Args:
        p_ksd_t: Kernel shared-data struct (for the SPC index chain).
        p_dph_t: PH thread state to append to.
        n: Source phoneme index in the unsubstituted stream.
        curr_outph: Output allophone code.
        curr_outstruc: Output feature struct (``U32`` in C, packed
            stress + boundary + word-pos bits).
        curr_indur: User-specified duration (ms), or 0 if absent.
        curr_inf0: User-specified F0 (Hz), or 0 if absent.
    """
    # SPC index chain bookkeeping (always do at minimum, per C comment).
    set_index_allo(p_ksd_t.spc_pkt_save, n, p_dph_t.nallotot)

    # Defensive bailout: don't write past n + 8 substitutions.
    if p_dph_t.nallotot > (n + _ALLO_DEFENSIVE_MARGIN):
        return

    # Grow the output buffers if needed.
    while len(p_dph_t.allophons) <= p_dph_t.nallotot:
        p_dph_t.allophons.append(0)
    while len(p_dph_t.allofeats) <= p_dph_t.nallotot:
        p_dph_t.allofeats.append(0)
    if p_dph_t.user_durs is None:
        p_dph_t.user_durs = []
    while len(p_dph_t.user_durs) <= p_dph_t.nallotot:
        p_dph_t.user_durs.append(0)
    if p_dph_t.user_f0 is None:
        p_dph_t.user_f0 = []
    while len(p_dph_t.user_f0) <= p_dph_t.nallotot:
        p_dph_t.user_f0.append(0)

    # Write the output triple.
    p_dph_t.allophons[p_dph_t.nallotot] = curr_outph
    p_dph_t.allofeats[p_dph_t.nallotot] = curr_outstruc
    p_dph_t.user_durs[p_dph_t.nallotot] = curr_indur

    if p_dph_t.f0mode != HAT_F0_SIZES_SPECIFIED:
        p_dph_t.user_f0[p_dph_t.nallotot] = curr_inf0

    # Cap nallotot at NPHON_MAX (silently drop further writes).
    if p_dph_t.nallotot < NPHON_MAX:
        p_dph_t.nallotot += 1


__all__ = ["make_out_phonol"]
