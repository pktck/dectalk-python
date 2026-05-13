"""``get_next_bound_type`` helper from ph_sort2.c.

Translated from ``src/dapi/src/ph/ph_sort2.c`` lines 187-211.

Scans the input symbol stream from ``msym + 1`` forward looking for
the next boundary phoneme (any code in ``[SBOUND, EXCLAIM]``). When
one is found, the matching :data:`~dectalk.ph.boundary_table.bounftab`
feature-bit flag is OR'd onto the *current output* phoneme's
``sentstruc[]`` entry via :func:`add_feature`, marking the upcoming
boundary type so downstream rules can tune timing / intonation.

The walk aborts early (without writing) if a syllabic phone is
encountered before any boundary symbol — boundaries set on the
*following* syllable's segment, never carry across an intervening
vowel.

Used by the PH sort pass (``ph_sort.c`` line 1462) right after a
syllable's tail consonant is committed to the output stream.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.phoneme_codes import EXCLAIM, SBOUND
from dectalk.ph.boundary_table import bounftab
from dectalk.ph.dph_t import DphT
from dectalk.ph.make_phone import add_feature
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature


def get_next_bound_type(p_dph_t: DphT, msym: int) -> None:
    """Mark the current output phoneme with the next-boundary feature.

    Faithful translation of:

    .. code-block:: c

        static void get_next_bound_type(LPTTS_HANDLE_T phTTS, short msym) {
            PDPH_T  pDph_t = phTTS->pPHThreadData;
            extern short bounftab[];
            short        m;

            for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                if (((pDph_t->symbols[m] & PVALUE) >= SBOUND)
                    && ((pDph_t->symbols[m] & PVALUE) <= EXCLAIM)) {
                    add_feature(pDph_t,
                                bounftab[pDph_t->symbols[m] - SBOUND],
                                (short)(CURRPHONE));
                    return;
                }
                else if (((phone_feature(pDph_t, pDph_t->symbols[m])) & FSYLL)
                         IS_PLUS) {
                    return;             /* Abort if see vowel first */
                }
            }
        }

    Notes on faithful detail:

    - ``CURRPHONE`` is the ``ph_sort.c`` per-file macro
      ``pDph_t->nphonetot - 1`` (the just-committed output phoneme).
    - The boundary-range check uses ``symbols[m] & PVALUE`` (low byte)
      but the ``bounftab`` lookup uses the **unmasked** ``symbols[m]``;
      this only differs for entries with a non-zero high byte, which
      never appears for the bare boundary codes 108..118.
    - ``IS_PLUS`` is the C ``!= 0`` macro.

    Args:
        p_dph_t: PH thread state.
        msym: Index of the current input symbol — scan starts from
            ``msym + 1``.
    """
    symbols = p_dph_t.symbols
    for m in range(msym + 1, p_dph_t.nsymbtot):
        if m >= len(symbols):
            break
        sym_val = symbols[m] & PVALUE
        if SBOUND <= sym_val <= EXCLAIM:
            # Look up the boundary's feature-bit flag.
            #
            # bounftab is sized 11 (SBOUND..EXCLAIM); since we just
            # range-checked sym_val ∈ [SBOUND, EXCLAIM], the index is
            # always valid.
            idx = symbols[m] - SBOUND
            if 0 <= idx < len(bounftab):
                add_feature(p_dph_t, bounftab[idx], p_dph_t.nphonetot - 1)
            return
        # Abort if we hit a vowel before the next boundary.
        if (phone_feature(symbols[m]) & FSYLL) != 0:
            return


__all__ = ["get_next_bound_type"]
