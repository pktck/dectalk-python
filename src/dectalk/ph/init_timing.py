"""``init_timing`` helper from ph_timng.c.

Translated from ``src/dapi/src/ph/ph_timng.c`` lines 174-310.

Called once per clause at the top of ``us_phtiming``. The function
rebuilds the per-clause timing scratch state from the current
speaking rate:

- Computes ``pDph_t->timeref`` (language-dependent reference period).
- Caches the linearised rate in ``pDphsettar->sprat0``.
- Computes ``sprat1`` (pause-scaling factor) and ``sprat2``
  (segment-duration compressibility) in Q14 fixed-point.
- Zeros ``pDph_t->longcumdur``.

The Q14 scaling factors are tuned by the C source's in-line comment
table for the ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``
branch:

- ``sprat0 = 180`` → ``sprat1 = 1.0``, ``sprat2 = 1.0`` (normal rate)
- ``sprat0 = 120`` → ``sprat1 = 1.5``, ``sprat2 = 1.25`` (slow)
- ``sprat0 = 300`` → ``sprat1 = 0.4``, ``sprat2 = 0.56`` (fast)

**Important**: the C comment table above describes the HLSYN
branch (``temp2 = 400 - sprat0``), but the shipped Linux
``libtts_us.so`` is built **without** ``HLSYN`` defined (see
``dectalkf_klsyn.h`` line 116-118: ``HLSYN`` is gated behind
``EPSON_ARM7``) and **without** ``CHANGES_AFTER_V43``. The active
branch is therefore ``temp2 = 425 - sprat0`` (issue #155). With
sprat0=180 that yields ``sprat1 = muldv(FRAC_ONE, 245, 220)
= 18245`` (≈ Q14 1.114), **not** the comment's nominal 1.0.

The C source has ``#ifdef SPANISH`` / ``ENGLISH_UK`` / ``SLOWTALK``
guards that adjust ``sprat0``; this port models the libtts_us.so
build (``ENGLISH_US`` defined, ``HLSYN`` / ``SPANISH`` /
``ENGLISH_UK`` / ``SLOWTALK`` undefined), so only the English-US
path is implemented.
"""

from __future__ import annotations

from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.math_helpers import muldv
from dectalk.ph.numeric_constants import FRAC_ONE


def init_timing(  # noqa: PLR0912 — faithful per-language dispatch with multiple branches.
    p_dph_t: DphT,
    pst_phsettar: DphSettarSt,
    *,
    sprate_ref: list[int],
    lang_curr: int,
) -> None:
    """Reset per-clause timing state from the current speaking rate.

    Faithful translation of:

    .. code-block:: c

        static void init_timing(LPTTS_HANDLE_T phTTS) {
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            PDPH_T pDph_t = phTTS->pPHThreadData;
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            int temp2, temp3;
            if (pKsd_t->sprate != pDphsettar->sprlast) {
                // language dispatch (only ENGLISH_US relevant here)
                if (pKsd_t->lang_curr == LANG_english)
                    pDph_t->timeref = 16000 / pKsd_t->sprate;
                // ... other languages adjust sprate first ...
                pDphsettar->sprlast = pKsd_t->sprate;
                if (pKsd_t->sprate > 250)
                    pDphsettar->sprat0 = 250 + ((pKsd_t->sprate - 250) >> 1);
                else
                    pDphsettar->sprat0 = pKsd_t->sprate;
                if (pDphsettar->sprat0 >= 180) {
                    temp3 = 220;
                    // libtts_us.so: HLSYN / CHANGES_AFTER_V43 both
                    // UNDEFINED — use the 425 branch (issue #155).
                    temp2 = 425 - pDphsettar->sprat0;
                } else {
                    temp3 = 120;
                    temp2 = 300 - pDphsettar->sprat0;
                }
                if (temp2 < 0) temp2 = 1;
                pDphsettar->sprat1 = muldv(FRAC_ONE, temp2, temp3);
                if (pDphsettar->sprat0 > 180) {
                    temp2 = 460 - pDphsettar->sprat0;
                    temp3 = 280;
                    if (temp2 <= 0) temp2 = 1;
                    pDphsettar->sprat2 = muldv(FRAC_ONE, temp2, temp3);
                } else {
                    pDphsettar->sprat2 =
                        ((unsigned) pDphsettar->sprat1 + FRAC_ONE) >> 1;
                }
            }
            pDph_t->longcumdur = 0;
        }

    Args:
        p_dph_t: PH thread state to update (``timeref``, ``longcumdur``).
        pst_phsettar: settar struct holding ``sprlast``, ``sprat0``,
            ``sprat1``, ``sprat2``.
        sprate_ref: Mutable 1-element list wrapping ``pKsd_t->sprate``.
            Other languages mutate it in place via ``pKsd_t->sprate +=
            20`` etc.; this list-wrapping preserves that aliasing.
        lang_curr: ``pKsd_t->lang_curr`` (``LANG_*`` code).
    """
    if sprate_ref[0] != pst_phsettar.sprlast:
        # Language dispatch (matches services.c ENGLISH_US build).
        if lang_curr == LANG_english:
            p_dph_t.timeref = 16000 // sprate_ref[0]
        elif lang_curr == LANG_british:
            sprate_ref[0] += 20
            p_dph_t.timeref = 16000 // sprate_ref[0]
        elif lang_curr == LANG_latin_american:
            sprate_ref[0] += 35
            p_dph_t.timeref = 4000 // sprate_ref[0]
        elif lang_curr == LANG_spanish:
            # Self-assignment "pKsd_t->sprate = pKsd_t->sprate" preserved
            # for fidelity (no observable change).
            p_dph_t.timeref = 16000 // sprate_ref[0]
        elif lang_curr == LANG_german:
            p_dph_t.timeref = 12000 // sprate_ref[0]
            sprate_ref[0] += 30
        elif lang_curr == LANG_french:
            sprate_ref[0] -= 20
            sprate_ref[0] = max(120, min(sprate_ref[0], 350))

        pst_phsettar.sprlast = sprate_ref[0]

        # Linearise high speaking rates (Fairbanks calibration).
        sprate = sprate_ref[0]
        if sprate > 250:  # noqa: PLR2004
            pst_phsettar.sprat0 = 250 + ((sprate - 250) >> 1)
        else:
            pst_phsettar.sprat0 = sprate

        # Compute sprat1 (additive-pause scaling).
        if pst_phsettar.sprat0 >= 180:  # noqa: PLR2004
            temp3 = 220
            # libtts_us.so on Linux builds with HLSYN and
            # CHANGES_AFTER_V43 both UNDEFINED (see
            # ``dectalkf_klsyn.h`` line 116-118 — ``HLSYN`` is gated
            # behind ``EPSON_ARM7``). The active C branch is therefore
            # ``temp2 = 425 - sprat0``; the comment-table "sprat1=1.0
            # at sprat0=180" describes the HLSYN branch which is dead
            # code on this build. Issue #155.
            temp2 = 425 - pst_phsettar.sprat0
        else:
            temp3 = 120
            temp2 = 300 - pst_phsettar.sprat0
        temp2 = max(1, temp2)
        pst_phsettar.sprat1 = muldv(FRAC_ONE, temp2, temp3)

        # Compute sprat2 (segment-duration compressibility).
        if pst_phsettar.sprat0 > 180:  # noqa: PLR2004
            temp2 = 460 - pst_phsettar.sprat0
            temp3 = 280
            temp2 = max(1, temp2)
            pst_phsettar.sprat2 = muldv(FRAC_ONE, temp2, temp3)
        else:
            # The C cast `((unsigned) sprat1 + FRAC_ONE) >> 1` treats
            # sprat1 as unsigned 16-bit. Replicate via a 16-bit mask.
            sprat1_u = pst_phsettar.sprat1 & 0xFFFF
            pst_phsettar.sprat2 = (sprat1_u + FRAC_ONE) >> 1

    # Zero clause-cumulative duration accumulator.
    p_dph_t.longcumdur = 0


__all__ = ["init_timing"]
