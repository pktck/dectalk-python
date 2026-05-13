"""``init_clause`` per-clause initialiser from ph_claus.c.

Translated from ``src/dapi/src/ph/ph_claus.c`` lines 517-543.

Per-clause initialisation hook the PH module's ``phclause`` driver
calls before walking the clause's symbol stream:

- On the very first clause (``ph_init == 0``), force a synth
  re-initialisation by setting ``loadspdef = TRUE``.
- When the next clause requests a speaker-definition reload
  (``loadspdef == TRUE``), prime ``nf0ev`` to ``-2`` so F0 jumps
  to the initial value; otherwise prime it to ``-1`` for weak
  re-initialisation.

The French-build ``cbsymbol`` reset is preserved as a comment but
not modelled (the Python port targets US English).
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT


def init_clause(p_dph_t: DphT) -> None:
    """Reset per-clause F0 / speaker-def init state.

    Faithful translation of the non-French branch of:

    .. code-block:: c

        static void init_clause(PDPH_T pDph_t) {
            if (pDph_t->ph_init == 0) {
                pDph_t->ph_init = 1;
                pDph_t->loadspdef = TRUE;  /* Force re-init */
            }
            if (pDph_t->loadspdef == TRUE) {
                pDph_t->nf0ev = -2;        /* F0 jumps to initial */
            } else {
                pDph_t->nf0ev = -1;        /* Weak init */
            }
        }

    Args:
        p_dph_t: PH thread state to mutate.
    """
    if p_dph_t.ph_init == 0:
        p_dph_t.ph_init = 1
        p_dph_t.loadspdef = 1  # TRUE — force re-init of synth.
    if p_dph_t.loadspdef == 1:
        p_dph_t.nf0ev = -2  # F0 jumps to initial value.
    else:
        p_dph_t.nf0ev = -1  # Weak init.


__all__ = ["init_clause"]
