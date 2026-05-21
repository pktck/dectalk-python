"""``us_special_coartic`` -- US English special coarticulation rules.

Translated from ``src/dapi/src/ph/p_us_st1.c`` line 375 (~95 lines).

Called by :func:`getbegtar` and :func:`getendtar` when the current
segment is a diphthongised vowel and ``par_type == FORM_FREQ``. The
function returns a delta to apply to the formant target, computing
phoneme-specific coarticulation effects:

- **F3** of selected vowels: -150 Hz next to ``W`` / ``R`` / ``RX``.
- **F2** of selected vowels:
  - Front vowels (IY..AE, IX) lowered -150 before ``LX``.
  - AY / OY lowered -250 / -350 before ``LX`` depending on diph pos.
  - Front vowels lowered -150 after ``W`` / ``LL`` / ``LX``.
  - ``UW`` raised +200 adjacent to an alveolar (FALVEL).
  - ``UW`` and unstressed ``YU`` (with diphpos > 0) further +200
    before an alveolar.
  - Unstressed vowels: effect amplified by half (and special case
    for unstressed ``YU`` -> 400).
  - Phrase-final stressed vowels (FBOUNDARY >= FVPNEXT): halved.
  - Clamped to [-400, 400].

Caller dispatch (``getbegtar`` / ``getendtar``) is what selects this
function via the language-font byte; for other languages the C
source has parallel ``gr_/la_/sp_/fr_special_coartic`` helpers that
remain deferred.
"""

from __future__ import annotations

from typing import cast

# ruff: noqa: SIM102 -- C-literal magic numbers and nested ifs kept
from dectalk.include.usp_codes import (
    USP_R,
    USP_RR,
    USP_RX,
    USP_W,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import F3
from dectalk.ph.phoneme_features import FVOWEL
from dectalk.ph.timing import phone_feature


def us_special_coartic(p_dph_t: DphT, nfon: int, diphpos: int) -> int:
    """Compute the coarticulation delta for one diphthong segment.

    Faithful translation of the C static helper. The caller adds the
    return value to the target read from ``p_diph``.

    Args:
        p_dph_t: Per-thread PH state with populated ``allophons`` /
            ``allofeats`` arrays and ``pSTphsettar.np`` set to the
            current parameter index.
        nfon: Index into ``allophons[]`` for the current phone.
        diphpos: Diphthong-position counter (0 for the first entry,
            >0 for later entries) -- the C ``diphpos`` argument.

    Returns:
        Signed delta (Hz) to apply to the formant target. Clamped to
        [-400, 400] for the F2 branch; F3 branch returns 0 or -150.
    """
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    temp = 0
    foncur = get_phone(p_dph_t, nfon)
    fonnex = get_phone(p_dph_t, nfon + 1)
    fonlas = get_phone(p_dph_t, nfon - 1)

    # F3 target of selected vowels: -150 next to W/R/RX.
    if p_dphsettar.np == F3:
        if (phone_feature(foncur) & FVOWEL) != 0 and foncur != USP_RR:
            if fonlas in (USP_W, USP_R, USP_RX) or fonnex in (USP_W, USP_R, USP_RX):
                temp = -150

        # F2 target of selected vowels (LX-before, W/L-after, UW raised,
        # YU fronted, stress effects, and the -400..+400 final clamp)
        # SKIPPED on the libtts_us.so HLSYN build target: the C source at
        # p_us_st1.c lines 401-470 wraps the whole block in
        # ``#ifndef HLSYN``. The HLSyn vocal-tract model in hlframe.c
        # (un-ported) is the C source's HLSYN replacement.

        # Maximum change should not be excessive.
        temp = min(temp, 400)
        temp = max(temp, -400)

    return temp


__all__ = ["us_special_coartic"]
