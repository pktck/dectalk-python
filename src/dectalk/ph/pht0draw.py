"""``pht0draw`` F0 contour generator from ph_drwt01.c.

Translated from ``src/dapi/src/ph/ph_drwt01.c`` line 2381 — the
**second** ``pht0draw`` definition, active for the production
``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build (``HLSYN``
undefined). (The first definition at line 277 is the ``NWSNOAA`` /
``ENGLISH_UK`` variant.)

Per-frame F0 (fundamental period) computation for the PH pipeline,
called once per 6.4 ms frame from the per-frame driver loop between
``phsettar`` and ``phdraw``.

This is a single function — the HLSYN ``ph_drwt02.c`` MALE/FEMALE split,
the separate ``filter_seg_commands`` two-pole, the ``f0s`` recombination,
and the triangle impulse envelope are all absent from the production
build. The flow is:

1. **Hard init** (``nf0ev <= -2``): set ``f0beginfall`` / ``f0endfall``
   from ``f0basefall`` (107 Hz ± half), prime the filter memories
   ``f0las1`` / ``f0las2`` to ``f0beginfall << F0SHFT``, load the 2-pole
   coefficients (``f0a2 = f0_lp_filter``).
2. **Soft init** (``nf0ev == -1``): re-prime the memories, set
   ``beginfall`` / ``endfall``, ``nframs = 12 - (f0_lp_filter >> 8)``.
3. **F0 command loop**: consume ``f0tar`` / ``f0tim`` (no f0type/f0length)
   while ``nfram >= dtimf0``. The command type is decoded from the value:
   ``0`` = reset, ``>= 2000`` = user note, even = STEP (``tarhat +=``),
   odd = IMPULSE (``tarimp = 2 * value``, a 16-frame doubled step).
4. **Baseline declination**: ``tarbas = beginfall - nframb``, falling
   0.1 Hz/frame toward ``endfall``.
5. **Segmental tracking**: advance the allophone pointer, look up
   ``us_f0segtars[phocur & PVALUE]`` (halved when unstressed), routed to
   ``tarseg`` (voiced) or the fast ``tarseg1`` (voiceless).
6. **Filter**: ``f0in = tarbas + tarhat + tarimp + tarseg``, decay
   ``tarseg`` 98%/frame, then the single 2-pole ``filter_commands``
   (which folds ``tarseg1`` into its second pole and writes ``f0`` /
   ``f0prime`` directly).
7. **Glottal-stop dip**, **scale** (``f0minimum + frac4mul(f0prime - 1200,
   f0scalefac)`` — the constant 1200 = 120 Hz baseline), **jitter**
   (``getcosine`` at ``timecos15``/``timecos10``, ``>> 5``).
8. **Emit** ``parstochip[OUT_T0] = muldv(400, 1000, f0prime)`` — the pitch
   *period* (the only essential divide in DECtalk; non-HLSYN build, so
   OUT_T0 carries the period, not f0prime).
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PVALUE
from dectalk.ph.cosine_tilt_tables import getcosine_tab
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS
from dectalk.ph.filter_commands import filter_commands
from dectalk.ph.getcosine import (
    F0SHFT,
    HIGHEST_F0,
    LOWEST_F0,
    TWOPI,
)
from dectalk.ph.inton_constants import SINGING
from dectalk.ph.linear_interp import linear_interp
from dectalk.ph.math_helpers import mlsh1, muldv
from dectalk.ph.numeric_constants import FRAC_ONE
from dectalk.ph.param_indices import OUT_DU, OUT_PH, OUT_T0
from dectalk.ph.phoneme_features import FPLOSV, FVOICD
from dectalk.ph.set_tglst import set_tglst
from dectalk.ph.set_user_target import set_user_target
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# ---------------------------------------------------------------------------
# Active segmental F0-target table from p_us_rom_dectalk_1996m_43f.c line 276.
# Indexed by ``phocur & PVALUE`` (the US allophone code). Differs from the
# HLSYN ph_drwt02.c us_f0msegtars table the port previously used.
# ---------------------------------------------------------------------------
_US_F0_SEGTARS: Final[tuple[int, ...]] = (
    # SI   IY   IH   EY   EH   AE   AA   AY   AW   AH
    50, 100,  60,  40,  20,   0,   0,   0,   0,  20,
    # AO   OW   OY   UH   UW   RR   YU   AX   IX   IR
    0,  30,  50,  60, 100,  50, 100,  30,  60, 100,
    # ER   AR   OR   UR    W    Y    R    L   HX   RX
    60,   0,  30,  80,  60,  60,   0,   0, 200,   0,
    # LX    M    N   NG   EL   D$   EN    F    V   TH
    0, -50, -50, -50,   0, -50, -50, 300, -50, 300,
    # DH    S    Z   SH   ZH    P    B    T    D    K
    -50, 300, -50, 300, -50, 300, -50, 300, -50, 300,
    # G   DX   TQ    Q   CH   JH   DF
    -50, -10,   0,   0, 300, -50, -10,
)  # fmt: skip


def _frac4mul(x: int, y: int) -> int:
    """``frac4mul(x, y)`` = ``((x) * (S32)(y)) >> 12`` from ph_defs.h."""
    return (x * y) >> 12


def pht0draw(ph_tts: TtsHandle) -> None:  # noqa: PLR0912, PLR0915 -- mirror C structure
    """Generate the next per-frame F0 and write ``parstochip[OUT_T0]``.

    Faithful translation of ``void pht0draw(LPTTS_HANDLE_T phTTS)``
    (ph_drwt01.c:2381). Mutates ``ph_tts.p_ph_thread_data`` (a
    :class:`DphT`) in place: writes ``parstochip[OUT_T0]`` (the pitch
    period), ``f0prime``, ``f0``, and ``avglstop``.

    Args:
        ph_tts: Engine handle; ``p_ph_thread_data`` must be a
            :class:`DphT` with ``pSTphsettar`` set to a
            :class:`DphSettarSt`.
    """
    p_dph_t = ph_tts.p_ph_thread_data
    if not isinstance(p_dph_t, DphT):
        return
    st = p_dph_t.pSTphsettar
    if not isinstance(st, DphSettarSt):
        return

    f0seg = 0
    f0in = 0
    pseudojitter = 0

    # --- 1. Hard init (nf0ev <= -2) — ph_drwt01.c:2404-2446 ----------------
    if p_dph_t.nf0ev <= -2:  # noqa: PLR2004 -- hard-init sentinel matches C
        st.f0beginfall = 1070 + (p_dph_t.f0basefall >> 1)  # 107 Hz plus
        st.f0endfall = 1070 - (p_dph_t.f0basefall >> 1)
        st.nframb = 0
        st.tglstp = -200
        st.phocur = GEN_SIL
        # Prime filter memory to the baseline (f0 in Hz*10).
        st.f0las1 = st.f0beginfall << F0SHFT
        st.f0las2 = st.f0beginfall << F0SHFT
        p_dph_t.f0 = st.f0beginfall
        st.tarhat = 0
        st.tarimp = 0
        # Critically-damped 2nd-order smoothing constants.
        st.f0a2 = p_dph_t.f0_lp_filter
        st.f0b = FRAC_ONE - p_dph_t.f0_lp_filter
        st.f0a1 = st.f0a2 << F0SHFT
        st.newnote = st.f0beginfall
        st.delnote = 0
        st.delcum = 0
        st.f0start = p_dph_t.f0
        st.vibsw = 0
        st.timecos10 = 0
        st.timecos15 = 0
        st.timecosvib = 0
        p_dph_t.nf0ev = -1

    # --- 2. Soft init (nf0ev == -1) — ph_drwt01.c:2449-2548 ----------------
    if p_dph_t.nf0ev == -1:
        st.f0las1 = st.f0beginfall << F0SHFT
        st.f0las2 = st.f0beginfall << F0SHFT
        st.beginfall = st.f0beginfall
        st.endfall = st.f0endfall
        st.nframb = 0
        # Raise baseline for first sentence of a paragraph.
        if p_dph_t.newparagsw != 0:
            st.beginfall += 120
            st.endfall += 70
            p_dph_t.newparagsw = 0
        st.dtimf0 = p_dph_t.f0tim[0] if p_dph_t.f0tim else 0
        st.np_drawt0 = -1
        st.npg = -1
        p_dph_t.nf0ev = 0
        # Offset cum dur to compensate for low-pass filter delay.
        st.nframs = 12 - (p_dph_t.f0_lp_filter >> 8)
        if p_dph_t.f0mode < SINGING:
            st.nfram = st.nframs >> 1  # Start note slightly early.
        else:
            st.nfram = 0
        st.nframg = 0
        st.extrad = 0
        st.segdur = 0
        st.segdrg = 0
        st.lastone = -1
        st.tarhat = 0  # Must be at bottom of hat.

    # --- 3. F0 command loop — ph_drwt01.c:2559-2663 ------------------------
    f0tar = p_dph_t.f0tar
    f0tim = p_dph_t.f0tim
    while st.nfram >= st.dtimf0 and p_dph_t.nf0ev < p_dph_t.nf0tot:
        f0command = f0tar[p_dph_t.nf0ev]
        st.nfram -= st.dtimf0
        p_dph_t.nf0ev += 1
        st.dtimf0 = f0tim[p_dph_t.nf0ev] if p_dph_t.nf0ev < len(f0tim) else 0

        if f0command == 0:
            # Reset baseline; go to bottom of hat pattern.
            st.nframb = 0
            st.tarhat = 0
        elif f0command >= 2000:  # noqa: PLR2004 -- user-note encoding boundary
            cmd_ref: list[int] = [f0command]
            set_user_target(p_dph_t, cmd_ref)
            f0command = cmd_ref[0]
        elif (f0command & 0o1) == 0:
            # Even -> STEP: accumulate into the hat.
            st.tarhat += f0command
            if f0command < 0:
                st.tarimp = 0  # Cancel previous impulse on a downward step.
        else:
            # Odd -> IMPULSE: realised as a 16-frame step of doubled amp.
            st.tarimp = f0command + f0command
            st.nimp = 16 - ((p_dph_t.f0_lp_filter - 1300) >> 8)

    # --- 4. Baseline declination — ph_drwt01.c:2668-2671 -------------------
    # Make baseline fall slowly (0.1 Hz / frame) until it reaches endfall.
    st.tarbas = st.beginfall - st.nframb
    if st.tarbas > st.endfall:
        st.nframb += 1

    # --- 5. Impulse countdown — ph_drwt01.c:2676 --------------------------
    st.nimp -= 1
    if st.nimp < 0:
        st.tarimp = 0

    # --- 6. Segmental tracking — ph_drwt01.c:2706-2774 --------------------
    if st.nframs >= (st.segdur + st.extrad) and st.np_drawt0 < (p_dph_t.nallotot - 1):
        st.nframs -= st.segdur
        st.np_drawt0 += 1
        np = st.np_drawt0
        st.segdur = p_dph_t.allodurs[np] if 0 <= np < len(p_dph_t.allodurs) else 0
        st.extrad = 0
        if 0 <= np < len(p_dph_t.allophons):
            st.phocur = p_dph_t.allophons[np]
        if 0 <= np + 1 < len(p_dph_t.allophons):
            st.phonex_drawt0 = p_dph_t.allophons[np + 1]
        # Next F0 segmental incremental target.
        code = st.phocur & PVALUE
        f0seg = _US_F0_SEGTARS[code] if 0 <= code < len(_US_F0_SEGTARS) else 0
        # Effect is less in unstressed segments.
        if 0 <= np < len(p_dph_t.allofeats) and (p_dph_t.allofeats[np] & FSTRESS) == 0:
            f0seg = f0seg >> 1
        # Delay start of f0 rise for an upcoming voiceless segment.
        if (phone_feature(st.phonex_drawt0) & FVOICD) == 0:
            st.extrad = 2
        # Delay f0 fall from a voiceless plosive until VOT.
        if (phone_feature(st.phocur) & FVOICD) == 0:
            st.tarseg1 = f0seg  # Fast gesture — only 1 lp filter pole.
            st.tarseg = 0
            st.extrad = 0
            if (phone_feature(st.phocur) & FPLOSV) != 0:
                st.extrad = 5
        else:
            st.tarseg = f0seg  # Slow gesture — both lp filter poles.
            st.tarseg1 = 0

    # --- 7. Glottal-stop gesture — ph_drwt01.c:2777 -----------------------
    set_tglst(p_dph_t)

    # --- 8. Filter f0 step/impulse commands to produce next f0 ------------
    # ph_drwt01.c:2779-2840
    if p_dph_t.f0mode < SINGING:
        f0in = st.tarbas + st.tarhat + st.tarimp + st.tarseg
        # Reduce segmental effect toward end of segment (98% per frame).
        p_dph_t.arg1 = st.tarseg
        p_dph_t.arg2 = 16064
        st.tarseg = mlsh1(st.tarseg, 16064)
        # The single 2-pole filter writes p_dph_t.f0 and p_dph_t.f0prime;
        # it folds st.tarseg1 into the second pole.
        filter_commands(p_dph_t, f0in)
    else:
        # Linear interpolation to 'newnote' over 100 ms or phoneme duration.
        linear_interp(p_dph_t)

    # --- 9. Glottalization dip — ph_drwt01.c:2844-2855 --------------------
    # F0 dip by 60 Hz linear ramp in 8 frames each direction about tglstp.
    dtglst = st.nframg - st.tglstp
    if dtglst < 0:
        dtglst = -dtglst
    if dtglst <= 7:  # noqa: PLR2004 -- C literal: glottal-stop half-width
        p_dph_t.f0prime += (dtglst * 70) - 550
    # Reduce AV somewhat (F0 computed before AV).
    if dtglst <= 5:  # noqa: PLR2004 -- C literal: AV-reduction half-width
        p_dph_t.avglstop = 6 - dtglst
    else:
        p_dph_t.avglstop = 0

    # --- 10. Bounds + scale — ph_drwt01.c:2860-2918 -----------------------
    if p_dph_t.f0prime > HIGHEST_F0:
        p_dph_t.f0prime = HIGHEST_F0
    elif p_dph_t.f0prime < LOWEST_F0:
        p_dph_t.f0prime = LOWEST_F0

    if p_dph_t.f0mode < SINGING:
        # Scale about the constant 1200 (= 120 Hz, nominal Paul AP).
        p_dph_t.f0prime = p_dph_t.f0minimum + _frac4mul(p_dph_t.f0prime - 1200, p_dph_t.f0scalefac)
        # Pseudo-jitter (approx 10/15-Hz sine waves, each +/- 0.5 Hz).
        st.timecos15 += 43  # Prime number to reduce coincidence.
        if st.timecos15 > TWOPI:
            st.timecos15 -= TWOPI
        st.timecos10 += 97
        if st.timecos10 > TWOPI:
            st.timecos10 -= TWOPI
        pseudojitter = getcosine_tab[st.timecos15 >> 6] + getcosine_tab[st.timecos10 >> 6]
        p_dph_t.f0prime += pseudojitter >> 5
        if p_dph_t.f0prime > HIGHEST_F0:
            p_dph_t.f0prime = HIGHEST_F0
        elif p_dph_t.f0prime < LOWEST_F0:
            p_dph_t.f0prime = LOWEST_F0
    elif p_dph_t.f0mode == SINGING:
        # Middle C = 256 Hz (A = 430.4) to A = 440 Hz.
        p_dph_t.f0prime = _frac4mul(p_dph_t.f0prime, 4190)

    # --- 11. Emit parstochip[OUT_T0] = pitch period — ph_drwt01.c:2922-2925
    # Non-HLSYN build: OUT_T0 carries the period muldv(400, 1000, f0prime),
    # not f0prime. f0prime is clamped to [LOWEST_F0, HIGHEST_F0] (>0) above,
    # so the divide is always safe.
    if len(p_dph_t.parstochip) > OUT_T0:
        p_dph_t.parstochip[OUT_T0] = muldv(400, 1000, p_dph_t.f0prime)

    # --- 12. Increment time counters — ph_drwt01.c:3017-3019 --------------
    st.nfram += 1
    st.nframs += 1
    st.nframg += 1

    # --- 13. OUT_PH / OUT_DU metadata overwrite — ph_drwt01.c:3021-3024 ---
    # (``#ifndef MSDOS``, active.) pht0draw re-stamps the packet metadata
    # cells from its OWN allophone pointer (``np_drawt0``, the F0-segment
    # walk) every frame, overriding the driver's phone-advance writes
    # (ph_claus.c:465-472; ``OUT_PH2`` keeps the driver value). This is
    # NOT audio-neutral, despite the #277 classification: the VTM's
    # limit-cycle ramp-down (vtm1.c:1318) gates on ``(variabpars[OUT_PH]
    # & PVALUE) == 0``, so silence muting follows the F0-segment pointer
    # — which leads/lags the driver's ``nphone`` by a few frames — not
    # the driver phone. Without this overwrite the ramp-down engages at
    # the wrong frame around every silence, diverging ~1100-1300 samples
    # per utterance-final (and comma-pause) boundary (issue #297).
    np = st.np_drawt0
    if 0 <= np < len(p_dph_t.allophons) and len(p_dph_t.parstochip) > OUT_DU:
        p_dph_t.parstochip[OUT_PH] = p_dph_t.allophons[np]
        p_dph_t.parstochip[OUT_DU] = p_dph_t.allodurs[np]


__all__ = ["pht0draw"]
