"""``us_special_rules`` -- special-case rules from p_us_st0.c.

Translated from ``src/dapi/src/ph/p_us_st0.c`` line 1234 (~160 lines).

**Variant note (issue #269).** The active klsyn build defines
``ENGLISH_US`` + ``OLD_SETTAR``, so ``ph_sttr1.c`` compiles
``p_us_st0.c`` -- NOT the ``p_us_st1.c`` rewrite an earlier port
followed. The st1 differences reverted here: NF60MS+floor CH/JH
closure clamp (st0: NF80MS cap only), the /th,dh,dz/ weak-burst hack
(absent in st0), area-parameter tspesh writes (absent in st0),
aspiration levels 52/55 keyed on phcur (st0: 57/61 keyed on phonex),
NF50MS default VOT with blade -2 and FSTRESS-gated NF7MS (st0:
NF40MS with FSTRESS_1-gated NF25MS), the USP_S s-cluster test (st0:
feature-word equality against FOBST+FCONSON plus struclm2), B1/B2
aspiration widening +500/+50 (st0: +250/+70), and voicebar AV
pspesh 10 (st0: 63). st0 also adds the homorganic plosive-nasal /
plosive-plosive burst suppression st1 dropped.

Called from :func:`phsettar`'s main loop AFTER the smooth-rule pass.
Handles three discrete event groups that don't fit the continuous
smoothing framework:

- **Rule 1: Burst duration** for plosives and affricates. Looks up
  the inherent burst duration via :func:`burdr`, suppresses it in
  homorganic plosive-nasal / plosive-plosive sequences, shortens it
  pre-obstruent or in short closures, clamps CH/JH closure to
  NF80MS, and writes ``closure_dur`` into ``tspesh`` of A2..AB.
- **Rule 2: Voice onset time** for aspirated plosives. Sets
  ``PAP.pspesh`` (aspiration amplitude, 57 or 61 before +back) based
  on ``begtyp`` of the next phone, computes ``vot`` (NF40MS default,
  NF25MS unstressed, NF15MS in s-clusters, longer in sonorant
  consonants) and writes it into ``PAV.tspesh`` / ``PAP.tspesh`` /
  ``PB1.tspesh`` / ``PB2.tspesh`` plus ``pspesh`` of B1/B2.
- **Rule 3: Voicebar** in voiced-plosive context to avoid pops.
  Sets ``PAV.tspesh`` (pspesh 63) and B1/B2/B3 tspesh+pspesh.
"""

from __future__ import annotations

# ruff: noqa: SIM102 -- nested ifs mirror the C source structure
from typing import cast

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.usp_codes import (
    USP_CH,
    USP_JH,
    USP_RR,
    USP_TX,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FBOUNDARY, FDUMMY_VOWEL, FSTRESS_1
from dectalk.ph.frame_counts import NF15MS, NF20MS, NF25MS, NF40MS, NF50MS, NF80MS
from dectalk.ph.numeric_constants import (
    A2,
    AB,
    AP,
    AV,
    B1,
    B2,
    B3,
)
from dectalk.ph.phoneme_features import (
    FBURST,
    FCONSON,
    FNASAL,
    FOBST,
    FPLOSV,
    FSONCON,
    FSONOR,
    FSYLL,
    FVOICD,
)
from dectalk.ph.rom_tables import us_place
from dectalk.ph.task_helpers import mstofr
from dectalk.ph.timing import begtyp, burdr, phone_feature
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
    del pholas, struclas  # kept for C-signature parity
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    param = p_dph_t.param

    # SPECIAL RULE 1: Burst duration for plosives and affricates.
    bdur = burdr(p_dphsettar.phcur)

    if (feacur & FBURST) != 0:
        bdur = mstofr(bdur)

        # Don't release the burst in a homorganic plosive-nasal or
        # plosive-plosive sequence (p_us_st0.c lines 1255-1261).
        if (feanex & (FNASAL | FPLOSV)) != 0:
            if us_place[p_dphsettar.phcur & PVALUE] == us_place[p_dphsettar.phonex & PVALUE]:
                bdur = 0

        if bdur > 1:
            if (feacur & FPLOSV) != 0 and (feanex & FOBST) != 0:
                bdur -= 1  # Shorten burst before obst by 6 ms.
            elif p_dph_t.durfon < NF50MS:
                bdur -= 1  # Shorten burst if closure short.

        closure_dur = p_dph_t.durfon - bdur

        # CH/JH closure clamp (st0: NF80MS cap, no lower floor; the
        # st1 rewrite used NF60MS with a floor of 2).
        if p_dphsettar.phcur in (USP_CH, USP_JH):
            closure_dur = min(closure_dur, NF80MS)

        # Walk PA2..PAB: zero fricative gains during closure. (st0
        # writes no area parameters here -- those are st1/HLSYN-era
        # additions.)
        for idx in range(A2, AB + 1):
            param[idx].tspesh = closure_dur
            param[idx].pspesh = 0
        # The np pointer in the C source ends the loop one past AB;
        # update p_dphsettar.np to mirror that final state.
        p_dphsettar.np = AB + 1

    # SPECIAL RULE 2: Voice onset time for aspirated plosives.
    vot = 0
    if (fealas & FPLOSV) != 0 and (fealas & FVOICD) == 0 and (feacur & FSONOR) != 0:
        # Aspiration amplitude in dB (st0: 57, or 61 before +back --
        # tested on the NEXT phone; st1 used 52/55 tested on phcur).
        param[AP].pspesh = 57
        if begtyp(p_dphsettar.phonex) != 1:
            param[AP].pspesh = 61

        param[AV].pspesh = 0  # Voicing during aspiration.

        # Asp dur for /p,t,k/ before stressed sonor (st0: NF40MS with
        # an FSTRESS_1-gated NF25MS reduction; st1 used NF50MS with a
        # blade-affected -2 and an FSTRESS-gated NF7MS).
        vot = NF40MS
        if (struccur & FSTRESS_1) == 0:
            vot = NF25MS  # Vot shorter if vowel not stressed.
            param[AP].pspesh -= 3

        if (feacur & FSONCON) != 0 or p_dphsettar.phcur == USP_RR:
            param[AP].pspesh += 3  # Aspiration stronger in sonor cons.

        # Plosive in an [s] cluster? st0 tests the raw feature word of
        # the phone two back for exact FOBST+FCONSON equality and the
        # struclm2 boundary bits (st1 compared against USP_S and read
        # allofeats[nphone-2] directly).
        if phone_feature(p_dph_t.allophons[p_dph_t.nphone - 2]) == (FOBST + FCONSON):
            if (struclm2 & FBOUNDARY) == 0:
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

        # Widen B1, B2 while glottis is open for aspiration
        # (st0: +250 / +70; st1 used +500 / +50).
        param[B1].tspesh = vot
        param[B2].tspesh = vot
        param[B1].pspesh = param[B1].tarcur + 250
        param[B2].pspesh = param[B2].tarcur + 70

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
        # Voicebar amplitude (st0: 63, "large since low-pass TILT
        # attenuates it"; the st1 rewrite reduced it to 10).
        param[AV].pspesh = 63
        param[B1].pspesh = 1000
        param[B2].pspesh = 1000
        param[B3].pspesh = 1500


__all__ = ["us_special_rules"]
