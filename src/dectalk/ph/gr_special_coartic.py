"""``gr_special_coartic`` -- German special coarticulation rules.

Translated from ``src/dapi/src/ph/p_gr_st1.c`` line 433 (~97 lines).

Called from :func:`make_dip` when the current segment is a diphthongised
vowel and ``par_type == FORM_FREQ``. Returns a delta to apply to the
formant target.

Only the F2 branch is active in the C source (no F3 special-case unlike
US). The block computes:

- **F2 lowered -150** for front vowels (``E``, ``AE``, ``I``, ``EH``,
  ``AEH``, ``IH``) before / after ``L``.
- **F2 lowered -250 / -350** for ``AU`` / ``EU`` diphthong depending on
  ``diphpos``.
- **F2 raised +200** for ``UE`` adjacent to an alveolar (``FALVEL``
  from ``gr_place``).
- **F2 raised +200** for ``UE`` / unstressed ``U`` (with ``diphpos > 0``)
  before an alveolar.
- Unstressed vowels: effect amplified by half (``temp += temp >> 1``).
  Unstressed ``U`` with ``diphpos > 0`` clamped to 400.
- Phrase-final stressed (``FBOUNDARY >= FVPNEXT``): effect halved.
- Final clamp to ``[-400, 400]``.

The first sub-test in both LX-before and LX-after branches reads:

.. code-block:: c

    if ((foncur == GRP_E) && (foncur == GRP_AE) || (foncur == GRP_I) ...)

which is a C-source bug (``&&`` between two equality checks of the same
variable is always false), so the first OR term collapses to false and
the effective check is ``(foncur == GRP_I) || (foncur == GRP_EH) ||
(foncur == GRP_AEH) || (foncur == GRP_IH)``. Mirror verbatim for parity.
"""

from __future__ import annotations

from typing import cast

# ruff: noqa: SIM102 -- C-literal magic numbers and nested ifs kept
from dectalk.include.cmd_codes import PVALUE
from dectalk.include.grp_codes import (
    GRP_AE,
    GRP_AEH,
    GRP_AU,
    GRP_E,
    GRP_EH,
    GRP_EU,
    GRP_I,
    GRP_IH,
    GRP_L,
    GRP_U,
    GRP_UE,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FSTRESS, FVPNEXT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import F2
from dectalk.ph.phoneme_features import FALVEL
from dectalk.ph.rom_tables import gr_place


def gr_special_coartic(p_dph_t: DphT, nfon: int, diphpos: int) -> int:
    """Compute the German coarticulation delta for one diphthong segment.

    Faithful translation of the C static helper. Caller adds the
    return value to the target read from ``p_diph``.

    Args:
        p_dph_t: Per-thread PH state with populated ``allofeats`` and
            ``pSTphsettar.np`` set to the current parameter index.
        nfon: Index into ``allophons[]`` for the current phone.
        diphpos: Diphthong-position counter (0 for the first entry,
            >0 for later entries).

    Returns:
        Signed delta (Hz) to apply to the formant target. Clamped to
        ``[-400, 400]`` for the F2 branch; returns 0 otherwise.
    """
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    temp = 0
    foncur = get_phone(p_dph_t, nfon)
    fonnex = get_phone(p_dph_t, nfon + 1)
    fonlas = get_phone(p_dph_t, nfon - 1)

    # F2 target of selected vowels.
    if p_dphsettar.np == F2:
        # Front vowel F2 target lowered before [L].
        if fonnex == GRP_L:
            # The C source's first conjunct ``(foncur == GRP_E) &&
            # (foncur == GRP_AE)`` is always false (same variable
            # compared against two distinct constants); mirror the
            # collapsed expression below.
            if (
                ((foncur == GRP_E) and (foncur == GRP_AE))
                or (foncur == GRP_I)
                or (foncur == GRP_EH)
                or (foncur == GRP_AEH)
                or (foncur == GRP_IH)
            ):
                temp = -150
            if ((foncur == GRP_AU) or (foncur == GRP_EU)) and (diphpos == 1):
                temp = -250
            if ((foncur == GRP_AU) or (foncur == GRP_EU)) and (diphpos > 1):
                temp = -350

        # Front vowel F2 target lowered after [L].
        # (C source has a commented-out W/LL/LX check; only [L] is active.)
        if fonlas == GRP_L:
            if (
                ((foncur == GRP_E) and (foncur == GRP_AE))
                or (foncur == GRP_I)
                or (foncur == GRP_EH)
                or (foncur == GRP_AEH)
                or (foncur == GRP_IH)
            ):
                temp = -150  # las and nex effects not cumulative

        # [UE] F2 target raised adjacent to an alveolar.
        if foncur == GRP_UE:
            if (gr_place[fonlas & PVALUE] & FALVEL) != 0:
                temp = 200

        if (foncur == GRP_UE) or ((foncur == GRP_U) and (diphpos > 0)):
            if (gr_place[fonnex & PVALUE] & FALVEL) != 0:
                temp += 200

        # Effects are greater for unstressed vowels.
        if (p_dph_t.allofeats[nfon] & FSTRESS) == 0:
            temp += temp >> 1
            # Unstressed U has a fronted U part.
            if (foncur == GRP_U) and (diphpos > 0):
                temp = 400
        # Reduce effects for phrase-final stressed vowels.
        elif (p_dph_t.allofeats[nfon] & FBOUNDARY) >= FVPNEXT:
            temp = temp >> 1

        # Maximum change should not be excessive.
        temp = min(temp, 400)
        temp = max(temp, -400)

    return temp


__all__ = ["gr_special_coartic"]
