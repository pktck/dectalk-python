# ruff: noqa: PLR2004
"""HL-to-LL Klatt parameter mapper.

Translated from ``src/dapi/src/hlsyn/hlframe.c`` (US-English build only).

This module is the central HL→LL conversion engine. One call to
:func:`hl_synthesize_ll_frame` maps one frame of HLSyn parameters
(areas, flows, formants, pressures) through:

1. :func:`tongue_acx_f1c` — tongue-body area → constriction area and
   adjusted F1.
2. ``SpeechCircuit`` — aerodynamic circuit solver (shimmed; see below).
3. :func:`_map_glottal_formants_not_f1` — copy F0/F2/F3/F4/F5 into the
   N-prefixed LL frame.
4. ``SetNasals_f1x`` — nasal pole/zero placement (shimmed; see below).
5. :func:`_source_amplitudes` — compute AV/AH/AF from subglottal pressure
   and glottal area.
6. :func:`_fricative_filters` — set parallel-branch filter gains from
   place-of-articulation.
7. :func:`_glottal_interaction` — compute F1/B1/B2/B3/B4/B5 from agf.
8. :func:`_source_specifics` — compute OQ/TL/DI.
9. :func:`unused_ll_parameters` — fill unused slots with fixed defaults.

Then the N-prefixed :class:`~dectalk.hlsyn.ll_frame_n.LLFrameN` is
transcribed into the plain :class:`~dectalk.hlsyn.llsyn.LLFrame` that
:func:`~dectalk.hlsyn.synthesize.ll_synthesize` consumes.

**Shimmed subsystems (German/French/Spanish and aerodynamic circuit).**
The aerodynamic circuit solver (``SpeechCircuit`` / ``circuit.c``) and
the nasal pole/zero placer (``SetNasals_f1x`` / ``nasalf1x.c``) are
multi-kloc subsystems whose full port is Phase E work.  Without
``SpeechCircuit`` we cannot compute ``state.agx`` / ``state.agf`` /
``state.Pm`` from first principles, so this port derives them from the
parstochip parameters that phdraw already computed. Specifically:

- ``state.Pm`` (mouth pressure, dynes/cm^2) is approximated as
  ``0`` when no glottal flow is happening.
- ``state.agf`` (glottal flow area) is taken from the phdraw-computed
  glottal area ``frame.ag`` directly.
- ``state.agx`` is set equal to ``state.agf``.
- ``state.f1x`` and ``state.b1x`` default to ``frame.f1`` and
  ``speaker.B1m`` respectively.

This means AV/AH gating (which depends on ``agf > agm``) works
correctly, while the full aerodynamic pressure calculation is deferred.
The formant/bandwidth adjustments in ``GlottalInteraction`` similarly
use the approximated ``agf``.

Non-US-English language branches (German, French, Spanish) are reached
via ``#ifdef`` guards that are never set in the Linux US-English build.
Their Python equivalents raise :exc:`NotImplementedError` with a C-line
citation; callers operating on US-English text will never hit those
branches.

C source: ``src/dapi/src/hlsyn/hlframe.c``
"""

from __future__ import annotations

import math

from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.hlsyn.llsyn import LLFrame
from dectalk.hlsyn.log10_table import dt_f_log10
from dectalk.hlsyn.place_constants import BLADE, DORSUM, LIPS, LIQUID
from dectalk.hlsyn.tongue_acx_f1c import tongue_acx_f1c
from dectalk.hlsyn.unused_ll_parameters import unused_ll_parameters
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

# --------------------------------------------------------------------------
# Constants from hlsyn.h
# --------------------------------------------------------------------------

#: Convert dynes/cm^2 (CGS) → cmH2O  (CGS = cmH2O * 980)
_CGS_TO_CMWATER: float = 1.0 / 980.0

#: Convert cmH2O → dynes/cm^2
_CMWATER_TO_CGS: float = 980.0

#: Convert mm^2 → cm^2
_MMSQ_TO_CMSQ: float = 0.01

#: Small positive float (FLT_MIN * 10 in C single-precision)
_FLOAT_EPS: float = 1.175494351e-37

#: Length epsilon (cm)
_L_EPS: float = 0.001


def _cgs_to_cmwater(cgs: float) -> float:
    """Inline of CGS_TO_CMWATER macro from hlsyn.h."""
    return cgs * _CGS_TO_CMWATER


def _cmwater_to_cgs(cmw: float) -> float:
    """Inline of CMWATER_TO_CGS macro from hlsyn.h."""
    return cmw * _CMWATER_TO_CGS


def _mmsq_to_cmsq(mmsq: float) -> float:
    """Inline of MMSQ_TO_CMSQ macro from hlsyn.h."""
    return mmsq * _MMSQ_TO_CMSQ


# --------------------------------------------------------------------------
# Private helpers (static functions in C)
# --------------------------------------------------------------------------


def _map_glottal_formants_not_f1(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Copy f0/f2/f3/f4/F5 to llframe; adjust f1c for tracheal coupling.

    Translated from ``hlframe.c`` lines 181-224 (``MapGlottalFormantsNotF1``).
    The ``#ifdef in_phdraw`` block (vowel-height / transglottal-pressure /
    stiffness corrections to NF0) is NOT active in the Linux US-English
    build and is therefore omitted here.
    """
    # hlframe.c line 185-209: copy f0 with rounding; clamp at 0.
    if frame.f0 > 0.0:
        nf0 = int(frame.f0 + 0.5)  # round via +0.5 + truncate, matching (short)
        llframe.NF0 = max(nf0, 0)
    else:
        llframe.NF0 = 0

    # hlframe.c lines 215-217: adjust f1c for tracheal coupling.
    # Only when nasal area is small (an < 3), f1c is in the low-F1 regime
    # (< 185 Hz), agf exceeds modal threshold, and f1c < tracheal pole F1T.
    if frame.an < 3.0 and state.f1c < 185.0 and state.agf > speaker.agm and state.f1c < speaker.F1T:
        state.f1c += speaker.KdF * (1.0 - state.f1c / speaker.F1T) * (state.agf - speaker.agm)

    # hlframe.c lines 219-223: copy f2/f3/f4/F5; C (short) cast truncates.
    llframe.NF2 = int(frame.f2)
    llframe.NF3 = int(frame.f3)
    llframe.NF4 = int(frame.f4)
    llframe.NF5 = int(speaker.F5)


def _fricative_filters(  # noqa: PLR0912, PLR0915
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Set parallel fricative filter gains from place-of-articulation.

    Translated from ``hlframe.c`` lines 227-401 (``FricativeFilters``).
    The BLADE/alveolar gains use the ``INVTMIONT`` branch which is NOT
    compiled in the standard Linux build. The DORSUM sub-cases are fully
    ported. The ``SetAlveolar`` table lookup (``#ifdef INVTMIONT``) is
    not active — US-English callers using BLADE location leave all BLADE
    parallel gains at zero (since ``#ifdef INVTMIONT`` is off in the
    production build).
    """
    # hlframe.c lines 234-239: zero all gains initially.
    llframe.NA2F = 0
    llframe.NA3F = 0
    llframe.NA4F = 0
    llframe.NA5F = 0
    llframe.NA6F = 0
    llframe.NAB = 0

    # hlframe.c lines 245-378: set gains if AF exceeds threshold.
    if speaker.AFThreshold < llframe.NAF:
        loc = state.loc

        if loc == LIPS:
            # hlframe.c line 250-252
            llframe.NAB = int(speaker.LabialAB)

        elif loc == BLADE:
            # INVTMIONT branch not compiled in Linux build — gains stay 0.
            # Full alveolar table lookup (ALVEOLAR macro) is under
            # ``#ifdef INVTMIONT`` (hlframe.c lines 262-278) which is
            # NOT defined; this branch is effectively a no-op.
            pass

        elif loc == DORSUM:
            # hlframe.c lines 283-349: palato-velar cases by frame.place.
            place = frame.place
            if place == 40:
                if frame.f2 > (
                    speaker.PalVelar_f2Offset + speaker.PalVelar_f2Overf3_Slope * frame.f3
                ):
                    llframe.NA3F = int(speaker.PalVelarA3F)
                else:
                    llframe.NA2F = 45
                    llframe.NA3F = 0
                    llframe.NA5F = 45
            elif place == 42:
                llframe.NA2F = 45
                llframe.NA3F = 0
                llframe.NA5F = 40
            elif place == 45:
                llframe.NA2F = 0
                llframe.NA3F = 45
                llframe.NA5F = 50
            elif place == 80:
                llframe.NA2F = 50
                llframe.NA3F = 0
                llframe.NA4F = 30
                llframe.NA5F = 30
            # C switch falls through DORSUM default → LIQUID (no break);
            # replicate that fall-through below.
            if frame.f3 < speaker.f3RetroflexMax:
                llframe.NA3F = int(speaker.RetroflexA3F)
            else:
                llframe.NA3F = int(speaker.LateralA3F)

        elif loc == LIQUID:
            # hlframe.c lines 351-358
            if frame.f3 < speaker.f3RetroflexMax:
                llframe.NA3F = int(speaker.RetroflexA3F)
            else:
                llframe.NA3F = int(speaker.LateralA3F)

        # hlframe.c lines 375-378: A6F always set when NAF > threshold.
        llframe.NA6F = int(speaker.A6f)

    # hlframe.c lines 386-387: F6 always set to speaker default.
    llframe.NF6 = int(speaker.F6)

    # hlframe.c lines 392-399: parallel fricative bandwidths.
    llframe.NB2F = int(speaker.B2F)
    llframe.NB3F = int(speaker.B3F)
    llframe.NB4F = int(speaker.B4F)
    llframe.NB5F = int(speaker.B5F)
    llframe.NB6F = int(speaker.B6F)
    # NDB1 used to bring in pressure rules (see C comment hlframe.c line 399):
    llframe.NDB1 = int(state.Pm)


def _interpolate_af(
    speaker: HLSpeaker,
    state: HLState,
    oldstate: HLState,
) -> float:
    """Compute AF via time-interpolation of acx and Pm.

    Translated from ``hlframe.c`` lines 499-571 (``InterpolateAF``).
    Returns 0.0 when ``state.agx <= 0`` or ``state.acx <= 0``.
    """
    if state.agx <= 0.0 or state.acx <= 0.0:
        return 0.0

    n_interp = int(speaker.UpdateInterval / speaker.AFInterpTimeStep)
    n_interp = max(n_interp, 1)

    acx_prev = _mmsq_to_cmsq(oldstate.acx)
    acx_step = (_mmsq_to_cmsq(state.acx) - acx_prev) / n_interp

    pm_prev = _cgs_to_cmwater(oldstate.Pm)
    pm_step = (_cgs_to_cmwater(state.Pm) - pm_prev) / n_interp

    max_af: float = 0.0
    af: float = 0.0

    for i in range(1, n_interp + 1):
        acx = acx_prev + i * acx_step
        pm = pm_prev + i * pm_step

        if pm < _FLOAT_EPS or acx < _FLOAT_EPS:
            af = 0.0
        else:
            af = 30.0 * dt_f_log10(pm) + 10.0 * dt_f_log10(acx) + speaker.Kf

        # hlframe.c lines 556-558: average (not max) in current code.
        max_af = (max_af + af) / 2.0

    max_af = max(max_af, 0.0)
    # Note: C source returns ``AF`` (last-iteration value), not ``MaxAF``.
    return af


def _source_amplitudes(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    oldstate: HLState,
    llframe: LLFrameN,
) -> None:
    """Compute AV / AH / AF from subglottal pressure and glottal area.

    Translated from ``hlframe.c`` lines 403-496 (``SourceAmplitudes``).
    All pressures in cmH2O; areas in mm^2 for inputs, converted via
    ``MMSQ_TO_CMSQ`` inside computations.
    """
    # ---- AF ----------------------------------------------------------------
    if frame.ag >= speaker.agHiKLSourceCutoff:
        llframe.NAF = 0
    else:
        llframe.NAF = int(_interpolate_af(speaker, state, oldstate))

    # ---- AV ----------------------------------------------------------------
    ps_minus_pm = frame.ps - _cgs_to_cmwater(state.Pm)

    av_zero = (
        state.agx < speaker.agMin
        or state.agx > speaker.agAVModalOffsetMax + speaker.agm
        or frame.ag >= speaker.agHiKLSourceCutoff
        or ps_minus_pm < _FLOAT_EPS
        or ps_minus_pm < speaker.AVPressureThreshold - speaker.KdPTdc * frame.dc
    )

    if av_zero:
        llframe.NAV = 0
    elif state.agx < speaker.agm:
        llframe.NAV = int(
            30.0 * dt_f_log10(ps_minus_pm)
            + speaker.Kv
            - speaker.KdAV0 * _mmsq_to_cmsq(speaker.agm - state.agx)
        )
    elif state.agx < speaker.agm + speaker.agAVModalOffsetOnOff:
        llframe.NAV = int(
            30.0 * dt_f_log10(ps_minus_pm)
            + speaker.Kv
            - speaker.KdAV * _mmsq_to_cmsq(state.agx - speaker.agm)
        )
    else:
        llframe.NAV = int(
            30.0 * dt_f_log10(ps_minus_pm)
            + speaker.Kv
            - speaker.KdAV * _mmsq_to_cmsq(speaker.agAVModalOffsetOnOff)
            - speaker.KdAV1 * _mmsq_to_cmsq(state.agx - speaker.agm - speaker.agAVModalOffsetOnOff)
        )

    # hlframe.c lines 461-466: clamp AV at 0; zero F0 when AV is 0.
    llframe.NAV = max(llframe.NAV, 0)
    if llframe.NAV == 0:
        llframe.NF0 = 0

    # ---- AH ----------------------------------------------------------------
    ps_abs = abs(frame.ps - _cgs_to_cmwater(state.Pm))

    ah_zero = (
        state.agf < speaker.agMin
        or frame.ag >= speaker.agHiKLSourceCutoff
        or (frame.an <= 0.0 and state.acx <= 0.0)
        or ps_abs < _FLOAT_EPS
        or state.agf < _FLOAT_EPS
    )

    if ah_zero:
        llframe.NAH = 0
    else:
        llframe.NAH = int(
            30.0 * dt_f_log10(ps_abs) + 10.0 * dt_f_log10(_mmsq_to_cmsq(state.agf)) + speaker.Ka
        )

    llframe.NAH = max(llframe.NAH, 0)


def _glottal_interaction(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Compute F1/B1/B2/B3/B4/B5 from glottal area and coupling.

    Translated from ``hlframe.c`` lines 573-638 (``GlottalInteraction``).
    """
    # hlframe.c line 577: F1 from f1x (nasal+constriction-adjusted F1).
    llframe.NF1 = int(state.f1x)

    # hlframe.c lines 578-591: B3/B4/B5 widen when agf > agm.
    if state.agf > speaker.agm:
        llframe.NB3 = int(speaker.B3m + (state.agf - speaker.agm) * speaker.KB3)
        llframe.NB4 = int(speaker.B4m + (state.agf - speaker.agm) * speaker.KB4)
        llframe.NB5 = int(speaker.B5m + (state.agf - speaker.agm) * speaker.KB5)
    else:
        llframe.NB3 = int(speaker.B3m)
        llframe.NB4 = int(speaker.B4m)
        llframe.NB5 = int(speaker.B5m)

    # hlframe.c lines 594-637: B1/B2 from aerodynamic coupling when agf > agm.
    if state.agf > speaker.agm:
        # Pre-computed constant: SPEEDSOUND^2 * sqrt(RHO/2) / PI
        # = 35400^2 * sqrt(0.00114/2) / PI = 9523445.0372631
        a = 9523445.0372631
        av = speaker.Av if speaker.Av > _L_EPS * _L_EPS else 3.5
        a /= av
        lv = speaker.Lv if speaker.Lv > _L_EPS else 17.0
        a /= lv

        # Pre-computed: 2 * PI^2 * RHO = 2.2502698034486e-2
        b = 2.2502698034486e-2 * speaker.Lvg * speaker.Lvg

        ptransg = abs(_cmwater_to_cgs(frame.ps) - state.Pm)

        f1x_sq = state.f1x * state.f1x
        f2_sq = frame.f2 * frame.f2
        agf_minus_agm_cmsq = _mmsq_to_cmsq(state.agf - speaker.agm)
        sqrt_ptransg = math.sqrt(ptransg) if ptransg > 0.0 else 0.0

        denom_f1 = ptransg + b * f1x_sq
        denom_f2 = ptransg + b * f2_sq
        llframe.NB1 = int(
            state.b1x + a * agf_minus_agm_cmsq * sqrt_ptransg / denom_f1
            if denom_f1 > 0.0
            else state.b1x
        )
        llframe.NB2 = int(
            speaker.B2m + a * agf_minus_agm_cmsq * sqrt_ptransg / denom_f2
            if denom_f2 > 0.0
            else speaker.B2m
        )
    else:
        llframe.NB1 = int(state.b1x)
        llframe.NB2 = int(speaker.B2m)


def _source_specifics(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Compute OQ / TL / DI.

    Translated from ``hlframe.c`` lines 640-738 (``SourceSpecifics``).
    """
    # ---- OQ ----------------------------------------------------------------
    oq = int(speaker.OQm + (state.agx - speaker.agm) * speaker.KOQ)
    if oq > speaker.OQMax:
        oq = int(speaker.OQMax)
    elif oq < speaker.OQMin:
        oq = int(speaker.OQMin)
    llframe.NOQ = oq

    # ---- TL ----------------------------------------------------------------
    acx_an_max = state.acx if state.acx > frame.an else frame.an
    if acx_an_max < speaker.TLBreakArea:
        tl_float = (
            speaker.TLm
            + ((speaker.TLBreakArea - acx_an_max) + (state.agx - speaker.agm)) * speaker.KTL
        )
    else:
        tl_float = speaker.TLm + (state.agx - speaker.agm) * speaker.KTL

    # hlframe.c lines 669-685: posterior glottal correction on TL.
    at = speaker.At if abs(speaker.At) > _L_EPS * _L_EPS else 2.5
    m = speaker.Lt / at

    av = speaker.Av if abs(speaker.Av) > _L_EPS else 3.5
    m += speaker.Lv / av

    ap_cgs = _mmsq_to_cmsq(frame.ap)
    ap_cgs2 = ap_cgs * ap_cgs

    ps_pm_abs = abs(_cmwater_to_cgs(frame.ps) - state.Pm)
    rk_ap_cubed_over_rho = math.sqrt(ps_pm_abs * 1754.385964912) * ap_cgs2

    rv_ap_cubed_over_rho = 2.0421052631578 * speaker.Lvg * speaker.Lhp * speaker.Lhp

    denom = rk_ap_cubed_over_rho + rv_ap_cubed_over_rho
    if denom > 0.0:
        six_k_hz_pi_t = 6000.0 * math.pi * ap_cgs2 * (m * ap_cgs + speaker.Lvg) / denom
    else:
        six_k_hz_pi_t = 1.0

    tl_float += 20.0 * dt_f_log10(six_k_hz_pi_t if six_k_hz_pi_t >= 1.0 else 1.0)

    # hlframe.c lines 718-727: formant spacing correction on TL.
    s_default = speaker.SDefault if speaker.SDefault > 0.0 else 1.0
    tl_float += (
        (speaker.SFromf4 * frame.f4 - s_default)
        * speaker.dBTLforPctS
        / (speaker.PctSfordBTL * s_default)
    )

    ntl = int(tl_float)
    if ntl > speaker.TLMax:
        ntl = int(speaker.TLMax)
    elif ntl < speaker.TLMin:
        ntl = int(speaker.TLMin)
    llframe.NTL = ntl

    # ---- DI ----------------------------------------------------------------
    if speaker.agDIMin < state.agx < speaker.agm:
        llframe.NDI = int(((speaker.agm - state.agx) / state.agx) * speaker.KDI)
    else:
        llframe.NDI = 0


def _llframe_n_to_llframe(llframe_n: LLFrameN) -> LLFrame:
    """Convert the N-prefixed intermediate frame to the synthesizer's LLFrame.

    Both structs carry the same Klatt parameters, but use different field
    name conventions: the N-prefixed struct (used by ``hlframe.c`` / the
    HL-to-LL bridge) has ``NF0``, ``NAV``, etc., while the synthesizer's
    struct (from ``llsyn.h``) has ``F0``, ``AV``, etc.
    """
    return LLFrame(
        F0=llframe_n.NF0,
        AV=llframe_n.NAV,
        OQ=llframe_n.NOQ,
        SQ=llframe_n.NSQ,
        TL=llframe_n.NTL,
        FL=llframe_n.NFL,
        DI=llframe_n.NDI,
        Ah=llframe_n.NAH,
        Af=llframe_n.NAF,
        F1=llframe_n.NF1,
        B1=llframe_n.NB1,
        DF1=llframe_n.NDF1,
        DB1=llframe_n.NDB1,
        F2=llframe_n.NF2,
        B2=llframe_n.NB2,
        F3=llframe_n.NF3,
        B3=llframe_n.NB3,
        F4=llframe_n.NF4,
        B4=llframe_n.NB4,
        F5=llframe_n.NF5,
        B5=llframe_n.NB5,
        F6=llframe_n.NF6,
        B6=llframe_n.NB6,
        FNP=llframe_n.NFNP,
        BNP=llframe_n.NBNP,
        FNZ=llframe_n.NFNZ,
        BNZ=llframe_n.NBNZ,
        FTP=llframe_n.NFTP,
        BTP=llframe_n.NBTP,
        FTZ=llframe_n.NFTZ,
        BTZ=llframe_n.NBTZ,
        A2f=llframe_n.NA2F,
        A3f=llframe_n.NA3F,
        A4f=llframe_n.NA4F,
        A5f=llframe_n.NA5F,
        A6f=llframe_n.NA6F,
        Ab=llframe_n.NAB,
        B2F=llframe_n.NB2F,
        B3F=llframe_n.NB3F,
        B4F=llframe_n.NB4F,
        B5F=llframe_n.NB5F,
        B6F=llframe_n.NB6F,
        ANV=llframe_n.NANV,
        A1V=llframe_n.NA1V,
        A2V=llframe_n.NA2V,
        A3V=llframe_n.NA3V,
        A4V=llframe_n.NA4V,
        ATV=llframe_n.NATV,
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def hl_synthesize_ll_frame(
    frame: HLFrame,
    oldframe: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    oldstate: HLState,
) -> LLFrame:
    """Map one HL frame to one LL Klatt frame.

    This is the Python equivalent of ``HLSynthesizeLLFrame`` in
    ``hlframe.c``.  It runs the complete chain for the US-English HLSYN
    build:

    1. ``tongue_acx_f1c`` — determine constriction area / location and
       adjust F1 for constrictions.
    2. (``SpeechCircuit`` shimmed — see module docstring.)
    3. ``_map_glottal_formants_not_f1`` — copy F0/F2/F3/F4/F5.
    4. (``SetNasals_f1x`` shimmed — nasal FNP/BNP uses LLFrameN defaults.)
    5. ``_source_amplitudes`` — compute AV / AF / AH.
    6. ``_fricative_filters`` — parallel branch filter gains.
    7. ``_glottal_interaction`` — B1 / B2 / B3 / B4 / B5 coupling.
    8. ``_source_specifics`` — OQ / TL / DI.
    9. ``unused_ll_parameters`` — zero/default unused slots.

    Args:
        frame: Current HL frame (areas, formants, pressures).
        oldframe: Previous HL frame (used by SpeechCircuit — shimmed here,
            kept for API compatibility with the C signature).
        speaker: HL speaker definition (modal bandwidths, thresholds,
            source constants, …).
        state: Mutable HL running state (agx/agf/Pm/f1c/f1x/b1x/…).
            Mutated in place by ``tongue_acx_f1c`` and
            ``_map_glottal_formants_not_f1``.
        oldstate: Previous HL state (used by ``_interpolate_af``).

    Returns:
        :class:`~dectalk.hlsyn.llsyn.LLFrame` ready for
        :func:`~dectalk.hlsyn.synthesize.ll_synthesize`.
    """
    # Step 1: tongue body → constriction area / f1c.
    # hlframe.c line 147: Tongue_acx_f1c(frame, speaker, state)
    tongue_acx_f1c(frame, speaker, state)

    # Step 2: SpeechCircuit — aerodynamic equivalent-circuit solver.
    # hlframe.c lines 152-153: SpeechCircuit(frame, oldframe, speaker, state, oldstate)
    # SHIMMED: SpeechCircuit is a multi-kloc subsystem (circuit.c) not yet
    # ported (Phase E). Without it, we cannot solve for state.Pm/agx/agf
    # from first principles. The caller sets agf=agx=frame.ag (phdraw glottal
    # area), Pm=0, and f1c/f1x/b1x=0. We fill f1x/b1x here if still zero.
    if state.f1x == 0.0:
        state.f1x = state.f1c if state.f1c > 0.0 else frame.f1
    if state.b1x == 0.0:
        state.b1x = speaker.B1m

    # Allocate the N-prefixed intermediate frame.
    llframe_n = LLFrameN()

    # Step 3: copy F0/F2/F3/F4/F5; optionally adjust f1c.
    # hlframe.c line 155: MapGlottalFormantsNotF1(frame, speaker, state, llframe)
    _map_glottal_formants_not_f1(frame, speaker, state, llframe_n)

    # Step 4: SetNasals_f1x — nasal pole/zero placement.
    # hlframe.c line 158: SetNasals_f1x(frame, speaker, state, llframe)
    # SHIMMED: nasalf1x.c not yet ported (Phase E). LLFrameN defaults
    # for NFNP/NBNP/NFNZ/NBNZ are 0, which removes those resonators.
    # (nasalf1x.c lines 1-200; citation: hlframe.c line 158)

    # Step 5: source amplitudes (AV / AF / AH).
    # hlframe.c line 162: SourceAmplitudes(frame, speaker, state, oldstate, llframe)
    _source_amplitudes(frame, speaker, state, oldstate, llframe_n)

    # Step 6: fricative filter gains.
    # hlframe.c line 165: FricativeFilters(frame, speaker, state, llframe)
    _fricative_filters(frame, speaker, state, llframe_n)

    # Step 7: glottal interaction (B1/B2/B3/B4/B5, F1).
    # hlframe.c line 168: GlottalInteraction(frame, speaker, state, llframe)
    _glottal_interaction(frame, speaker, state, llframe_n)

    # Step 8: OQ / TL / DI.
    # hlframe.c line 171: SourceSpecifics(frame, speaker, state, llframe)
    _source_specifics(frame, speaker, state, llframe_n)

    # Step 9: zero / default the unused LL slots.
    # hlframe.c line 174: UnusedLLParameters(llframe)
    unused_ll_parameters(llframe_n)

    # Convert N-prefixed frame to the synthesizer's LLFrame.
    return _llframe_n_to_llframe(llframe_n)


# Alias under the original C-source name for inventory and parity tests.
HLSynthesizeLLFrame = hl_synthesize_ll_frame

__all__ = [
    "HLSynthesizeLLFrame",
    "hl_synthesize_ll_frame",
]
