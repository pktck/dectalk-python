"""``sp_special_coartic`` -- Spanish special coarticulation rules.

Translated from ``src/dapi/src/ph/p_sp_st1.c`` line 343 (~245 lines).

Called from :func:`make_dip` when the current segment is a diphthongised
vowel and ``par_type == FORM_FREQ``. The function returns the sum of
two ``span_spec_coart`` calls (vowel paired with previous and next
phone) -- a symmetric per-vowel rule table.

The helper :func:`span_spec_coart` (defined in p_sp_st1.c lines
388-588) is the Spanish nonsense-syllable coarticulation table:

- **F1**: ``E`` next to ``M`` returns -50.
- **F2**: per-vowel switch with place-of-articulation
  (``sp_place[other & PVALUE]``) and per-consonant cases.
- **F3**: per-vowel switch covering Spanish nasals, liquids, velars.

All other vowel/parameter combinations return 0.
"""

from __future__ import annotations

from typing import cast

# ruff: noqa: PLR0911, PLR0912, PLR0915, SIM102 -- C-literal switch-cases preserved
from dectalk.include.cmd_codes import PVALUE
from dectalk.include.spp_codes import (
    SPP_A,
    SPP_CH,
    SPP_E,
    SPP_F,
    SPP_G,
    SPP_GH,
    SPP_I,
    SPP_IX,
    SPP_J,
    SPP_K,
    SPP_LL,
    SPP_M,
    SPP_N,
    SPP_NH,
    SPP_O,
    SPP_S,
    SPP_U,
    SPP_Y,
    SPP_YH,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import F1, F2, F3
from dectalk.ph.phoneme_features import FDENTAL, FLABIAL, FPALATL, FVELAR
from dectalk.ph.rom_tables import sp_place


def span_spec_coart(p_dph_t: DphT, vowel: int, other: int) -> int:
    """Spanish vowel-pair coarticulation rule (vowel x other phone).

    Faithful translation of the C static helper. The "rule" was derived
    by examining a table of nonsense syllables; it applies after general
    coarticulation. Called only for vowels.

    Args:
        p_dph_t: Per-thread PH state with ``pSTphsettar.np`` set.
        vowel: Current phoneme (Spanish font byte).
        other: Other (previous or next) phoneme.

    Returns:
        Signed F1/F2/F3 delta in Hz, or 0 if no rule fires.
    """
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)

    # IX (nasal offglide) treated as NH for place lookup.
    if other == SPP_IX:
        other = SPP_NH
    loc = sp_place[other & PVALUE]

    if p_dphsettar.np == F1:
        # E + M -> -50. Reintroduced 30-Jul-86 ("me" sounded like "mi" without it).
        if vowel == SPP_E and other == SPP_M:
            return -50
    elif p_dphsettar.np == F2:
        if vowel == SPP_A:
            if loc == FLABIAL:
                pass
            else:
                if other in (SPP_CH, SPP_YH, SPP_Y, SPP_NH):
                    return 100
                if other == SPP_J:
                    return -50
        elif vowel == SPP_E:
            # EAB 7/15/98 -- "eu" diphthong lowers achieved E F2 target.
            if other == SPP_U:
                return -300
        elif vowel == SPP_I:
            # EAB 7/16/98 -- double-vowel diphthong: I + O -> -200.
            if other == SPP_O:
                return -200
        elif vowel == SPP_O:
            # OUT 30-Apr-86 to prevent overload; back in 30-Jul-86.
            if loc == FLABIAL and other != SPP_F:
                return -50
            if other in (SPP_Y, SPP_YH):
                return 100
        elif vowel == SPP_U:
            # OUT 30-Apr-86 to prevent overload; back in 30-Jul-86.
            if other in (SPP_M, SPP_F):
                return -50
            if loc == FDENTAL or other == SPP_S or loc == FPALATL:  # noqa: SIM109
                return 75
    elif p_dphsettar.np == F3:
        if vowel == SPP_A:
            if loc == FLABIAL and other != SPP_M:
                return -100
            elif loc == FDENTAL:
                return 75
            elif loc == FVELAR:
                return -75
            else:
                if other == SPP_N:
                    return 200
                if other == SPP_S:
                    return 100
                if other in (SPP_LL, SPP_Y):
                    return -200
                if other == SPP_NH:
                    return 50
        elif vowel == SPP_E:
            if other == SPP_M:
                return 300
            if other == SPP_N:
                return 150
            if other == SPP_LL:
                return -50
            if other == SPP_NH:
                return 75
            if other in (SPP_K, SPP_G, SPP_GH):
                return 150
            if other == SPP_I:
                return -250  # EAB 7/20/98: Spanish "ie" diphthong
        elif vowel == SPP_I:
            if other in (SPP_M, SPP_NH, SPP_N):
                return 150
            if other == SPP_O:
                return -100
        elif vowel == SPP_O:
            if other == SPP_M:
                return 75
            if other == SPP_N:
                return 175
            if other == SPP_NH:
                return 125
            if other in (SPP_Y, SPP_YH):
                return 100
            if other in (SPP_J, SPP_F):
                pass  # break out of the switch (no return)
            elif loc == FLABIAL:
                return -50
            elif loc == FVELAR:
                return -100
        elif vowel == SPP_U:
            if other in (SPP_M, SPP_N, SPP_NH, SPP_LL, SPP_G, SPP_GH):
                return -75

    return 0


def sp_special_coartic(p_dph_t: DphT, nfon: int, diphpos: int) -> int:
    """Compute the Spanish coarticulation delta for one diphthong segment.

    Calls :func:`span_spec_coart` once for the current vowel paired with
    the previous phone and once for the current vowel paired with the
    next phone, returning the sum (symmetric rule).

    Args:
        p_dph_t: Per-thread PH state with populated ``allofeats`` and
            ``pSTphsettar.np`` set to the current parameter index.
        nfon: Index into ``allophons[]`` for the current phone.
        diphpos: Diphthong-position counter (unused by the C body, kept
            for signature parity).

    Returns:
        Signed delta (Hz) to apply to the formant target.
    """
    del diphpos  # unused -- mirrors C source (passed but ignored)
    foncur = get_phone(p_dph_t, nfon)
    fonnex = get_phone(p_dph_t, nfon + 1)
    fonlas = get_phone(p_dph_t, nfon - 1)

    # This assumes that changes are mostly symmetric.
    temp = span_spec_coart(p_dph_t, foncur, fonlas)
    temp += span_spec_coart(p_dph_t, foncur, fonnex)
    return temp


__all__ = ["sp_special_coartic", "span_spec_coart"]
