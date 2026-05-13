"""Per-clause done-check from ph_claus.c.

Translated from ``src/dapi/src/ph/ph_claus.c`` lines 649-677.

:func:`exit_if_done` checks whether the phoneme cursor has run
past the end of the allophone array, and if so zeroes the
``user_durs`` / ``user_f0`` / ``user_offset`` arrays so the next
``phclause()`` entry starts clean.

Returns ``True`` if the clause is finished, ``False`` otherwise.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT


def exit_if_done(p_dph_t: DphT) -> bool:
    """Return True iff the phoneme cursor has reached the end.

    Faithful translation of:

    .. code-block:: c

        static int exit_if_done(PDPH_T pDph_t) {
            short n;
            if (pDph_t->nphone >= pDph_t->nallotot) {
                for (n = 0; n <= pDph_t->nsymbtot; n++) {
                    pDph_t->user_durs[n] = 0;
                    pDph_t->user_f0[n] = 0;
                    pDph_t->user_offset[n] = 0;
                }
                return TRUE;
            }
            return FALSE;
        }

    The C source clears the three per-symbol arrays in-place; the
    Python port mirrors that, indexing through the window-pointer
    aliases ``user_durs`` / ``user_f0`` / ``user_offset``.

    Args:
        p_dph_t: PH thread-state instance to mutate.

    Returns:
        True if ``nphone >= nallotot`` (clause finished), False
        otherwise.
    """
    if p_dph_t.nphone < p_dph_t.nallotot:
        return False

    # Walk i = 0 .. nsymbtot inclusive and zero the three arrays.
    # The window-pointer aliases are list[int] | None; the C source
    # has them pre-seeded by init_phclause, so they should be non-None
    # by the time exit_if_done runs. Guard for safety.
    n_last = p_dph_t.nsymbtot
    durs = p_dph_t.user_durs
    f0 = p_dph_t.user_f0
    offset = p_dph_t.user_offset
    for n in range(n_last + 1):
        if durs is not None and n < len(durs):
            durs[n] = 0
        if f0 is not None and n < len(f0):
            f0[n] = 0
        if offset is not None and n < len(offset):
            offset[n] = 0
    return True


__all__ = ["exit_if_done"]
