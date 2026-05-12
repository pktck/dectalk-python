"""Syllable-boundary assignment from ls_adju.c.

Translated from ``src/dapi/src/lts/ls_adju.c``:

- :func:`ls_adju_sylables` — walk a PHONE list backwards from each
  PFSYLAB boundary, marking leftward consonants as PFLEFTC and
  shifting the syllable boundary to maximise the onset cluster
  (English maximal-onset principle).

The C source uses ``ls_adju_cluster`` (already translated) to
decide whether a 2-consonant cluster is legal, with a special
``TRYS`` exception for "s"/"sh" stop clusters like "spr", "str".
The English ``US_S``/``US_SH`` constants come from
:class:`dectalk.include.phoneme_codes.USPhoneme`.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.cluster_check import ILLEGAL, TRYS, ls_adju_cluster
from dectalk.lts.phone_list import SNONE
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import PFLEFTC, PFMORPH, PFSYLAB, Phone

_US_S: int = int(USPhoneme.S)
_US_SH: int = int(USPhoneme.SH)


def ls_adju_sylables(fpp: Phone, lpp: Phone | None) -> None:  # noqa: PLR0912, PLR0915 — straight-line port of C
    """Place syllable boundaries with maximal-onset clusters.

    Faithful translation of:

    .. code-block:: c

        void ls_adju_sylables(PHONE *fpp, PHONE *lpp) {
            PHONE *pp1, *pp2, *lsp;
            int type, stype;
            lsp = NULL;
            pp1 = fpp;
            // Find first PFSYLAB.
            while (pp1 != lpp) {
                if ((pp1->p_flag & PFSYLAB) != 0) { lsp = pp1; break; }
                pp1 = pp1->p_fp;
            }
            while (pp1 != fpp) {
                stype = SNONE;
                do {
                    pp2 = pp1->p_bp;
                    if (ls_adju_is_cons(pp2) == FALSE) break;
                    pp1 = pp2;
                    if (pp1->p_stress != SNONE) {
                        stype = pp1->p_stress;
                        pp1->p_stress = SNONE;
                    }
                } while (pp1 != fpp);
                // ... maximal-onset cluster logic, see C source ...
                pp1->p_flag |= PFSYLAB;
                pp1->p_stress = stype;
                lsp = pp1;
            }
        }

    Modifies the PHONE list in place: marks consonants in the onset
    as PFLEFTC, transfers stress codes to the syllable-initial
    PHONE, and re-positions PFSYLAB flags to maximise the onset.

    Mutates ``fpp`` and the PHONE chain reachable via ``p_bp``
    pointers; does not return anything.

    Args:
        fpp: First PHONE in the word.
        lpp: Sentinel (one past the last PHONE), or None for "end of chain".
    """
    # Find the first PFSYLAB boundary going forward.
    pp1: Phone | None = fpp
    lsp: Phone | None = None
    while pp1 is not lpp and pp1 is not None:
        if (pp1.p_flag & PFSYLAB) != 0:
            lsp = pp1
            break
        pp1 = pp1.p_fp
    if pp1 is None:
        return

    # Walk backwards until we hit the start of the word.
    while pp1 is not fpp:
        stype = SNONE  # Stress to transfer to the new boundary.
        # Back up to the nearest vowel (skip consonants).
        while True:
            pp2 = pp1.p_bp
            if pp2 is None or not ls_adju_is_cons(pp2.p_sphone):
                break
            pp1 = pp2
            if pp1.p_stress != SNONE:
                stype = pp1.p_stress
                pp1.p_stress = SNONE
            if pp1 is fpp:
                break
        if pp1 is fpp:
            # "gdansk", "gxx" — onset all the way to the start.
            if lsp is not None:
                lsp.p_flag &= ~PFSYLAB
                stype = lsp.p_stress
                lsp.p_stress = SNONE
            pp1.p_flag |= PFSYLAB
            pp1.p_stress = stype
            break

        # ``pp1`` is now at a vowel; back up one step to a consonant.
        pp1 = pp1.p_bp  # type: ignore[assignment]  # known non-None: ls_adju_is_cons confirmed
        if pp1 is None:
            return
        pp1.p_flag |= PFLEFTC
        if pp1.p_stress != SNONE:
            stype = pp1.p_stress
            pp1.p_stress = SNONE

        pp2 = pp1.p_bp
        if (
            (pp1.p_flag & PFMORPH) != 0
            or pp1 is fpp
            or pp2 is None
            or not ls_adju_is_cons(pp2.p_sphone)
        ):
            pp1.p_flag |= PFSYLAB
            pp1.p_stress = stype
            lsp = pp1
            continue

        # Try 2-consonant onset.
        pp1 = pp2
        pp1.p_flag |= PFLEFTC
        if pp1.p_stress != SNONE:
            stype = pp1.p_stress
            pp1.p_stress = SNONE

        pp2 = pp1.p_bp
        if (
            (pp1.p_flag & PFMORPH) != 0
            or pp1 is fpp
            or pp2 is None
            or not ls_adju_is_cons(pp2.p_sphone)
        ):
            pp1.p_flag |= PFSYLAB
            pp1.p_stress = stype
            lsp = pp1
            continue

        # Check legality of the 2-consonant cluster.
        # ``pp1`` is the right consonant, ``pp2`` is the left one we'd add.
        # The C source orders as cluster(pp2, pp1) — left then right.
        cluster_type = ls_adju_cluster(pp2.p_sphone, pp1.p_sphone)
        if cluster_type == ILLEGAL:
            pp1.p_flag |= PFSYLAB
            pp1.p_stress = stype
            lsp = pp1
            continue

        # Try adding the left consonant to the cluster.
        pp1 = pp2
        pp1.p_flag |= PFLEFTC
        if pp1.p_stress != SNONE:
            stype = pp1.p_stress
            pp1.p_stress = SNONE

        # TRYS clusters allow an additional leading "s"/"sh".
        if cluster_type == TRYS and (pp1.p_flag & PFMORPH) == 0 and pp1 is not fpp:
            pp2 = pp1.p_bp
            if pp2 is not None and pp2.p_sphone in (_US_S, _US_SH):
                pp1 = pp2
                pp1.p_flag |= PFLEFTC
                if pp1.p_stress != SNONE:
                    stype = pp1.p_stress
                    pp1.p_stress = SNONE

        pp1.p_flag |= PFSYLAB
        pp1.p_stress = stype
        lsp = pp1


__all__ = ["ls_adju_sylables"]
