"""``us_special_rules`` -- special-case rules from p_us_st1.c.

Translated from ``src/dapi/src/ph/p_us_st1.c`` line 1296 (~256 lines).

Called from :func:`phsettar`'s main loop AFTER the smooth-rule pass.
Handles three discrete event groups that don't fit the continuous
smoothing framework:

- **Rule 1: Burst duration** for plosives and affricates. Looks up
  the inherent burst duration via :func:`burdr`, shortens it
  pre-obstruent or in short closures, clamps CH/JH closure, and
  writes ``closure_dur`` into ``tspesh`` of A2..AB. Sets the
  appropriate area parameter (``AREAL`` / ``AREAB`` / ``TONGUEBODY``
  -- only ``AREAL`` / ``AREAB`` for the non-NEW_VTM build) per place
  of articulation (labial / blade-affected / velar). Also a weak-
  burst kluge for /th, dh, dz/.
- **Rule 2: Voice onset time** for aspirated plosives. Sets
  ``PAP.pspesh`` (aspiration amplitude) based on ``begtyp`` of the
  current phone, computes ``vot`` (NF50MS default, adjusted by
  ``BLADEAFFECTED`` place / stress / cluster context / dummy-vowel
  release), and writes ``vot`` into ``PAV.tspesh`` / ``PAP.tspesh``
  / ``PB1.tspesh`` / ``PB2.tspesh`` plus ``pspesh`` of B1/B2.
- **Rule 3: Voicebar** in voiced-plosive context to avoid pops.
  Sets ``PAV.tspesh`` and B1/B2/B3 tspesh+pspesh.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.usp_codes import (
    USP_CH,
    USP_DH,
    USP_DZ,
    USP_JH,
    USP_RR,
    USP_S,
    USP_TH,
    USP_TX,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FDUMMY_VOWEL, FSTRESS, FSTRESS_1
from dectalk.ph.frame_counts import NF7MS, NF15MS, NF20MS, NF50MS, NF60MS
from dectalk.ph.numeric_constants import (
    A2,
    A6,
    AB,
    AP,
    AREAB,
    AREAL,
    AV,
    B1,
    B2,
    B3,
)
from dectalk.ph.phoneme_features import (
    BLADEAFFECTED,
    FBURST,
    FLABIAL,
    FOBST,
    FPLOSV,
    FSONCON,
    FSONOR,
    FSYLL,
    FVELAR,
    FVOICD,
)
from dectalk.ph.rom_tables import us_place
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import begtyp, burdr, place
from dectalk.ph.tts_handle import TtsHandle


def us_special_rules(  # noqa: PLR0912, PLR0915
    phTTS: TtsHandle,  # noqa: N803
    fealas: int,
    feacur: int,
    feanex: int,
    struclm2: int,
    struccur: int,
    pholas: int,
    struclas: int,
) -> None:
    """Apply the three special-case rules atop the smooth-rule pass.

    Faithful translation of the C static helper. Writes ``tspesh`` /
    ``pspesh`` slots on multiple ``Parameter`` entries.
    """
    del struclm2, pholas, struclas  # kept for C-signature parity
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    param = p_dph_t.param

    # SPECIAL RULE 1: Burst duration for plosives and affricates.
    bdur = burdr(p_dphsettar.phcur)

    if (feacur & FBURST) != 0:
        bdur = mstofr(bdur)

        if bdur > 1:
            if (feacur & FPLOSV) != 0 and (feanex & FOBST) != 0:
                bdur -= 1  # Shorten burst before obst by 6 ms.
            elif p_dph_t.durfon < NF50MS:
                bdur -= 1  # Shorten burst if closure short.

        closure_dur = p_dph_t.durfon - bdur

        if p_dphsettar.phcur in (USP_CH, USP_JH):
            closure_dur = min(closure_dur, NF60MS)
            # Fast-speech kluge: keep some closure.
            closure_dur = max(closure_dur, 2)

        # Walk PA2..PAB: zero fricative gains during closure.
        for idx in range(A2, AB + 1):
            param[idx].tspesh = closure_dur
            param[idx].pspesh = 0

        # On the last iteration (np == &PAB) write the area params.
        place_bits = us_place[p_dphsettar.phcur & PVALUE]
        if place_bits & FLABIAL:
            param[AREAL].tspesh = closure_dur
            param[AREAB].tspesh = 0
        elif place_bits & BLADEAFFECTED:
            param[AREAL].tspesh = 0
            param[AREAB].tspesh = closure_dur
        elif place_bits & FVELAR:
            param[AREAL].tspesh = 0
            param[AREAB].tspesh = 0
        # The np pointer in the C source ends loop one past AB; we
        # update p_dphsettar.np to mirror that final state.
        p_dphsettar.np = AB + 1

    # Special hack: weak burst for /th, dh, dz/.
    if p_dphsettar.phcur in (USP_TH, USP_DH, USP_DZ):
        for idx in range(A6, AB + 1):
            param[idx].tspesh = p_dph_t.durfon - 2
            param[idx].pspesh = 30
        p_dphsettar.np = AB + 1

    # SPECIAL RULE 2: Voice onset time for aspirated plosives.
    vot = 1
    if (fealas & FPLOSV) != 0 and (fealas & FVOICD) == 0 and (feacur & FSONOR) != 0:
        param[AP].pspesh = 57 - 5  # Aspiration amplitude (dB).

        # Stronger asp before +back vowel.
        if begtyp(p_dphsettar.phcur) != 1:
            param[AP].pspesh = 55

        param[AV].pspesh = 0  # Voicing during aspiration.

        vot = NF50MS  # Default asp dur for /p,t,k/ before stressed sonor.

        # Subtract 2 frames if previous phone has blade-affected place.
        if place(p_dph_t.allophons[p_dph_t.nphone - 1]) & BLADEAFFECTED:
            vot -= 2

        if (struccur & FSTRESS) == 0:
            vot = NF7MS  # Vot shorter if vowel unstressed.
            param[AP].pspesh -= 3

        if (feacur & FSONCON) != 0 or p_dphsettar.phcur == USP_RR:
            param[AP].pspesh += 3  # Aspiration stronger in sonor cons.

        # Plosive in an [s] cluster?
        if p_dph_t.allophons[p_dph_t.nphone - 2] == USP_S:
            if (p_dph_t.allofeats[p_dph_t.nphone - 2] & FBOUNDARY) == 0:
                vot = NF15MS
        elif (feacur & FSYLL) == 0:
            vot += NF20MS  # Vot longer in a sonorant consonant.

        if vot >= p_dph_t.durfon:
            vot = p_dph_t.durfon - 1

        # Cap: vot can't exceed half of a stressed vowel's duration.
        if vot > (p_dph_t.durfon >> 1) and (feacur & FSYLL) != 0 and (struccur & FSTRESS_1) != 0:
            vot = p_dph_t.durfon >> 1

        # Dummy vowel releases a voiceless plosive into silence.
        if (struccur & FDUMMY_VOWEL) != 0:
            vot = p_dph_t.durfon
            param[AP].pspesh -= 3

        param[AV].tspesh = vot
        param[AP].tspesh = vot

        # Widen B1, B2 while glottis is open for aspiration.
        param[B1].tspesh = vot
        param[B2].tspesh = vot
        param[B1].pspesh = param[B1].tarcur + 250 + 250
        param[B2].pspesh = param[B2].tarcur + (70 - 20)

    # SPECIAL RULE 3: Realistic voicebar.
    if (
        (feacur & FBURST) != 0
        and (feacur & FVOICD) != 0
        and (fealas & FVOICD) != 0
        and (feanex & FVOICD) == 0
        and p_dphsettar.phcur != USP_TX
    ):
        param[AV].tspesh = p_dph_t.durfon - NF15MS
        param[B1].tspesh = p_dph_t.durfon
        param[B2].tspesh = p_dph_t.durfon
        param[B3].tspesh = p_dph_t.durfon
        param[AV].pspesh = 10
        # p_us_st1.c lines 1542-1550: the HLSYN build (libtts_us.so,
        # our target) sets B1/B2/B3 pspesh to 1000/1000/1500. The
        # FAKE_HLSYN build uses 150 across the board -- a much
        # narrower voicebar bandwidth. Mirrors HLSYN since that's
        # what the binary on disk produces.
        param[B1].pspesh = 1000
        param[B2].pspesh = 1000
        param[B3].pspesh = 1500


__all__ = ["us_special_rules"]
