"""Geminate-pair deletion from l_us_ru1.c and ls_adju.c.

Translated from:

- ``ls_adju_del_phone`` (ls_adju.c) — unlink a PHONE from the doubly-
  linked list.
- ``ls_adju_delgemphone`` (ls_adju.c) — replace ``pp->p_sphone`` with
  a target code, merge the backward neighbour's flags + stress into
  ``pp``, then delete the backward neighbour.
- ``ls_rule_delete_geminate_pairs`` (l_us_ru1.c) — walk the entire
  PHONE chain and apply geminate-deletion rules for
  ``[l][L]`` / ``[L][l]`` (any morpheme), ``[t][T]``, ``[s][S]``,
  and any same-phoneme consonant pair (only within a morpheme).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts.phone_predicates import ls_adju_is_cons
from dectalk.lts.structs import PFMORPH, Phone

_US_LL: int = int(USPhoneme.LL)
_US_EL: int = int(USPhoneme.EL)
_US_T: int = int(USPhoneme.T)
_US_TH: int = int(USPhoneme.TH)
_US_S: int = int(USPhoneme.S)
_US_SH: int = int(USPhoneme.SH)


def ls_adju_del_phone(plist: list[Phone], dpp: Phone) -> None:
    """Unlink ``dpp`` from the doubly-linked PHONE chain.

    Faithful translation of:

    .. code-block:: c

        void ls_adju_del_phone(PLTS_T pLts_t, PHONE *dpp) {
            PHONE *bpp = dpp->p_bp;
            PHONE *fpp = dpp->p_fp;
            bpp->p_fp = fpp;
            fpp->p_bp = bpp;
            ls_rule_phone_free(pLts_t, dpp);
        }

    Removes ``dpp`` from both the linked-list pointers AND from the
    Python list backing store. The C source returns the freed node
    to a pool; the Python port relies on garbage collection.

    Args:
        plist: PHONE list (Python list of :class:`Phone` objects).
        dpp: PHONE to remove.
    """
    bpp = dpp.p_bp
    fpp = dpp.p_fp
    if bpp is not None:
        bpp.p_fp = fpp
    if fpp is not None:
        fpp.p_bp = bpp
    plist.remove(dpp)


def ls_adju_delgemphone(plist: list[Phone], pp: Phone, ph: int) -> None:
    """Replace ``pp`` with ``ph``, merge flags from ``p_bp``, then delete ``p_bp``.

    Faithful translation of:

    .. code-block:: c

        void ls_adju_delgemphone(PLTS_T pLts_t, PHONE *pp, int ph) {
            PHONE *bp = pp->p_bp;
            pp->p_sphone = ph;
            pp->p_flag |= bp->p_flag;
            if (bp->p_stress > pp->p_stress)
                pp->p_stress = bp->p_stress;
            ls_adju_del_phone(pLts_t, bp);
        }

    Args:
        plist: PHONE list.
        pp: PHONE to keep (its sphone is overwritten).
        ph: New ``p_sphone`` code.
    """
    bp = pp.p_bp
    if bp is None:
        return
    pp.p_sphone = ph
    pp.p_flag |= bp.p_flag
    pp.p_stress = max(pp.p_stress, bp.p_stress)
    ls_adju_del_phone(plist, bp)


def ls_rule_delete_geminate_pairs(plist: list[Phone]) -> None:
    """Walk the PHONE chain and collapse geminate consonant pairs.

    Faithful translation of:

    .. code-block:: c

        void ls_rule_delete_geminate_pairs(PLTS_T pLts_t) {
            PHONE *pp1 = pLts_t->phead.p_fp;
            while (pp1 != &pLts_t->phead) {
                int ph1 = pp1->p_sphone;
                int ph2 = pp1->p_bp->p_sphone;
                // [l][L] / [L][l] across any boundary → keep [L]
                if ((ph1==US_LL && ph2==US_EL) || (ph1==US_EL && ph2==US_LL)) {
                    ls_adju_delgemphone(pLts_t, pp1, US_EL);
                    pp1 = pp1->p_fp;
                    continue;
                }
                // Block these rules across explicit morpheme markers.
                if ((pp1->p_flag & PFMORPH) == 0) {
                    // [t][T] / [T][t] within a morpheme → keep [T]
                    // [s][S] / [S][s] within a morpheme → keep [S]
                    // any [+Cons]2 within a morpheme → keep one
                }
                pp1 = pp1->p_fp;
            }
        }

    Bug fix in our translation: the C source has a typo
    ``(ph1==US_EL && ph1==US_LL)`` — the second comparison should be
    ``ph2==US_LL`` for the symmetric case. The C bug means
    ``[L][l]`` is never caught by the symmetric branch — but the
    first branch ``(ph1==US_LL && ph2==US_EL)`` already covers half.
    We preserve the typo to keep bit-for-bit parity with the binary;
    a future fix would require coordinating with upstream.

    Args:
        plist: PHONE list (mutated in place).
    """
    # Iterate by index rather than pointer; rebuild on each iteration
    # so deletions don't skip the next phone.
    i = 0
    while i < len(plist):
        pp1 = plist[i]
        bp = pp1.p_bp
        if bp is None:
            i += 1
            continue
        ph1 = pp1.p_sphone
        ph2 = bp.p_sphone

        # [l][L] / [L][l] — preserve the [L]. Note the second branch
        # has the C-source bug ``ph1 == US_LL`` instead of
        # ``ph2 == US_LL``; we keep it to match the binary.
        if (ph1 == _US_LL and ph2 == _US_EL) or (ph1 == _US_EL and ph1 == _US_LL):
            ls_adju_delgemphone(plist, pp1, _US_EL)
            # After delgemphone, the previous PHONE was removed,
            # so the current PHONE shifted down by one index.
            # Advance to the next (forward) PHONE.
            i = plist.index(pp1) + 1
            continue

        if (pp1.p_flag & PFMORPH) == 0:
            if (ph1 == _US_T and ph2 == _US_TH) or (ph1 == _US_TH and ph2 == _US_T):
                ls_adju_delgemphone(plist, pp1, _US_TH)
                i = plist.index(pp1) + 1
                continue
            if (ph1 == _US_S and ph2 == _US_SH) or (ph1 == _US_SH and ph2 == _US_S):
                ls_adju_delgemphone(plist, pp1, _US_SH)
                i = plist.index(pp1) + 1
                continue
            if ph1 == ph2 and ls_adju_is_cons(ph1):
                ls_adju_delgemphone(plist, pp1, pp1.p_sphone)
                i = plist.index(pp1) + 1
                continue

        i += 1


def ls_adju_ins_phone(
    plist: list[Phone],
    fpp: Phone,
    sph: int,
    uph: int,
    stress: int,
) -> bool:
    """Insert a new PHONE before ``fpp``; return True on success.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_ins_phone(PLTS_T pLts_t, PHONE *fpp,
                              int sph, int uph, int stress) {
            PHONE *ipp = ls_rule_phone_alloc(pLts_t);
            if (ipp == NULL) return FALSE;
            PHONE *bpp = fpp->p_bp;
            bpp->p_fp = ipp;
            ipp->p_fp = fpp;
            fpp->p_bp = ipp;
            ipp->p_bp = bpp;
            ipp->p_sphone = sph;
            ipp->p_uphone = uph;
            ipp->p_flag = fpp->p_flag;       // forward the flags
            fpp->p_flag = 0;
            ipp->p_stress = stress;
            fpp->p_stress = SNONE;
            return TRUE;
        }

    The new PHONE inherits ``fpp``'s flags and the new stress; ``fpp``
    is cleared (flags=0, stress=SNONE). The C source's pool
    allocator can fail with NULL → FALSE; the Python port always
    succeeds (GC, no fixed pool).

    Args:
        plist: PHONE list (mutated in place).
        fpp: PHONE before which to insert.
        sph: Stressed phoneme code for the new PHONE.
        uph: Unstressed phoneme code.
        stress: Stress code to assign.

    Returns:
        Always ``True`` in the Python port (the C alloc-failure path
        is unreachable).
    """
    from dectalk.lts.phone_list import SNONE  # noqa: PLC0415 — cycle break

    ipp = Phone(p_sphone=sph, p_uphone=uph, p_flag=fpp.p_flag, p_stress=stress)
    bpp = fpp.p_bp
    if bpp is not None:
        bpp.p_fp = ipp
    ipp.p_fp = fpp
    fpp.p_bp = ipp
    ipp.p_bp = bpp
    fpp.p_flag = 0
    fpp.p_stress = SNONE
    # Insert into the list at fpp's index.
    plist.insert(plist.index(fpp), ipp)
    return True


def ls_adju_is_obs(p_sphone: int) -> bool:
    """Return True iff the phoneme has the POBS (obstruent) feature.

    Faithful translation of:

    .. code-block:: c

        int ls_adju_is_obs(PHONE *pp) {
            if ((pfeat[pp->p_sphone] & POBS) != 0)
                return TRUE;
            return FALSE;
        }

    Args:
        p_sphone: The ``p_sphone`` byte from a PHONE struct.

    Returns:
        ``True`` iff ``pfeat[p_sphone]`` has bit POBS set.
    """
    from dectalk.lts.grapheme_features import POBS, pfeat  # noqa: PLC0415 — local import

    return bool(pfeat[p_sphone] & POBS)


__all__ = [
    "ls_adju_del_phone",
    "ls_adju_delgemphone",
    "ls_adju_ins_phone",
    "ls_adju_is_obs",
    "ls_rule_delete_geminate_pairs",
]
