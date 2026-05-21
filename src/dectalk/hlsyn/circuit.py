"""Aerodynamic equivalent-circuit solver from hlsyn/circuit.c.

Translated from ``src/dapi/src/hlsyn/circuit.c`` (coded by J. Erik Moore,
2/94; last modified 25 Mar 1998 by reb).

:func:`speech_circuit` analyses the lumped-element speech-production
circuit to compute the mouth pressure ``Pm``, the wall capacitance
pressure ``Pcw``, and the aerodynamic flows that the HL synthesiser
needs for source amplitude gating (AV / AH) and formant-1 correction.

The circuit models:

- A kinematic glottal resistance whose effective area ``agf`` varies
  with mouth pressure (via the glottal compliance ``Cg``).
- A parallel oral-constriction resistance of area ``acx``.
- A nasal shunt resistance of area ``an``.
- A pharyngeal-wall branch consisting of a wall resistance ``Rw`` in
  series with a wall capacitance ``Cw`` (whose "charge" ``Pcw`` is a
  running state quantity).

The nonlinear ODE is stiff for small ``Cw``, so an implicit trapezoidal
step is used (see the long comment in ``circuit.c`` for the derivation).
That reduces the per-time-step problem to a single nonlinear scalar
equation in ``Pm`` solved by Brent's method via
:func:`~dectalk.hlsyn.brent.brent` and
:func:`~dectalk.hlsyn.brent.brent_bracket`.

Unit conventions (inherited verbatim from the C source):

- Areas: **mm^2** in the ``HLFrame`` / ``HLState`` fields;
  converted to **cm^2** internally via ``MMSQ_TO_CMSQ = * 0.01``.
- Subglottal pressure ``ps``: **cm H₂O** in ``HLFrame``;
  converted to **CGS (dynes/cm^2)** via ``CMWATER_TO_CGS = * 980``.
- Flows: **cm³/s** (CGS).
- Pressures (``Pm``, ``Pcw``): **dynes/cm²** (CGS).

Public entry point
------------------
:func:`speech_circuit` — matches the C signature
``void SpeechCircuit(HLFrame *, HLFrame *, HLSpeaker *, HLState *, HLState *)``.
"""
# ruff: noqa: N803, N806, PLR0915, PLR2004 — preserve C-source variable names and magic literals

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.hlsyn.brent import brent, brent_bracket
from dectalk.hlsyn.pm_root_args import PmRootFunctionArgs
from dectalk.hlsyn.pm_root_function import pm_root_function
from dectalk.hlsyn.sqrt_table import dt_f_sqrt

if TYPE_CHECKING:
    from dectalk.ph.hl_speaker import HLSpeaker
    from dectalk.ph.hlsyn_structs import HLFrame, HLState

# ---------------------------------------------------------------------------
# Constants (from hlsyn.h / circuit.c).
# ---------------------------------------------------------------------------

# ``sqrt(2 / RHO)`` where ``RHO = 0.00114 g/cm³``.  Pre-computed literal
# from circuit.c line 224.
_ROOT_TWO_OVER_RHO: float = 41.885390829169

# ``RHO`` in CGS (g/cm³).
_RHO: float = 0.00114

# Brent's method tolerances (from hlsyn.h).
_CIRCUIT_TOL: float = 2.0e-3  # Root tolerance (non-LOWCOMPUTE build).
_BRENT_DEFAULT_ITMAX: int = 100
_BRENT_DEFAULT_EPS: float = 3.0e-4
_BRENT_BRACKET_DEFAULT_FACTOR: float = 1.6
_BRENT_BRACKET_DEFAULT_NTRY: int = 50

# Unit-conversion multipliers (from hlsyn.h macros).
_MMSQ_TO_CMSQ: float = 0.01
_CMWATER_TO_CGS: float = 980.0


def _mmsq_to_cmsq(x: float) -> float:
    return x * _MMSQ_TO_CMSQ


def _cmwater_to_cgs(x: float) -> float:
    return x * _CMWATER_TO_CGS


def _flow_sqrt(x: float) -> float:
    """``FLOW_SQRT(x)`` — sign-preserving square root via the LUT."""
    return dt_f_sqrt(x)


def _next_uw(Pm: float, args: PmRootFunctionArgs) -> float:
    """``NEXT_Uw(Pm, p)`` — implicit-Euler linearised wall flow."""
    return args.A * Pm - args.B


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def speech_circuit(
    frame: HLFrame,
    oldframe: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    oldstate: HLState,
) -> None:
    """Analyse the speech circuit for ``Pm``, ``agx``, ``agf``, and flows.

    Faithful translation of ``void SpeechCircuit(HLFrame *frame,
    HLFrame *oldframe, HLSpeaker *speaker, HLState *state,
    HLState *oldstate)`` from ``src/dapi/src/hlsyn/circuit.c``
    (lines 151-324).

    Updates *in place* on ``state``:

    - ``state.Pm``   — mouth pressure (dynes/cm²)
    - ``state.Pcw``  — wall-capacitance pressure (dynes/cm²)
    - ``state.Cg``   — glottal compliance (adjusted by dc)
    - ``state.Cw``   — wall compliance (adjusted by dc)
    - ``state.agx``  — tracheal-adjusted glottal area (mm²)
    - ``state.agf``  — flow glottal area = agx + ap (mm²)
    - ``state.Ug``   — glottal flow (cm³/s)
    - ``state.Uacx`` — oral-constriction flow (cm³/s)
    - ``state.Un``   — nasal flow (cm³/s)
    - ``state.Uw``   — wall flow (cm³/s)

    Args:
        frame:    Current HLSyn parameter frame.
        oldframe: Previous HLSyn parameter frame.
        speaker:  Voice-specific speaker constants.
        state:    Running HLState to update.
        oldstate: Running HLState from the previous frame (read-only).
    """
    # ------------------------------------------------------------------
    # Choose number of sub-interpolations (matches circuit.c lines 168-183).
    # ------------------------------------------------------------------
    if oldstate.Pm <= 2.0e3:
        num_interp = 1
        divider = 1.0
    elif oldstate.Pm < 4.0e3:
        num_interp = 2
        divider = 0.5
    else:
        num_interp = 4
        divider = 0.25

    # ------------------------------------------------------------------
    # Set up interpolation steps (circuit.c lines 185-209).
    # Areas are converted from mm² to cm² for the internal solve.
    # Negative ``an`` is clamped to zero (25 Mar 1998 fix).
    # ------------------------------------------------------------------
    agprev = _mmsq_to_cmsq(oldframe.ag)
    agstep = (_mmsq_to_cmsq(frame.ag) - agprev) * divider

    acxprev = _mmsq_to_cmsq(oldstate.acx)
    acxstep = (_mmsq_to_cmsq(state.acx) - acxprev) * divider

    anprev = max(0.0, _mmsq_to_cmsq(oldframe.an))
    anstep = (max(0.0, _mmsq_to_cmsq(frame.an)) - anprev) * divider

    ueprev = oldframe.ue
    uestep = (frame.ue - ueprev) * divider

    apprev = _mmsq_to_cmsq(oldframe.ap)
    apstep = (_mmsq_to_cmsq(frame.ap) - apprev) * divider

    psprev = _cmwater_to_cgs(oldframe.ps)
    psstep = (_cmwater_to_cgs(frame.ps) - psprev) * divider

    # Update state.Cg / state.Cw (dc-adjusted compliances).
    state.Cg = speaker.Cgm + speaker.KCg * 0.01 * frame.dc * speaker.Cgm
    Cgprev = oldstate.Cg
    Cgstep = (state.Cg - Cgprev) * divider

    state.Cw = speaker.Cwm + speaker.KCw * 0.01 * frame.dc * speaker.Cwm
    Cwprev = oldstate.Cw
    Cwstep = (state.Cw - Cwprev) * divider

    # ------------------------------------------------------------------
    # Compute deltaT / 2 for the implicit trapezoidal step.
    # ------------------------------------------------------------------
    delta_t_over_2 = 0.5 * speaker.UpdateInterval * divider

    # ------------------------------------------------------------------
    # Pre-compute the root-finding payload (circuit.c lines 224-234).
    # ------------------------------------------------------------------
    other_args = PmRootFunctionArgs(
        rootTwoOverRho=_ROOT_TWO_OVER_RHO,
        Lg=speaker.Lg,
    )

    # Initialise running state from previous frame.
    Pm = oldstate.Pm
    Pcw = oldstate.Pcw
    Uw = oldstate.Uw
    # Non-negative clamp on Cw (circuit.c line 234).
    other_args.Cw = 0.0 if oldstate.Cw < 0.0 else oldstate.Cw

    # ------------------------------------------------------------------
    # Sub-interpolation loop (circuit.c lines 236-295).
    # ------------------------------------------------------------------
    for interp in range(1, num_interp + 1):
        # Update per-interpolation parameters.
        other_args.ag = agprev + agstep * interp
        other_args.acx = acxprev + acxstep * interp
        other_args.an = anprev + anstep * interp
        other_args.ap = apprev + apstep * interp
        other_args.ap = max(0.0, other_args.ap)  # non-negative clamp
        other_args.ue = ueprev + uestep * interp
        other_args.ps = psprev + psstep * interp
        other_args.Cg = Cgprev + Cgstep * interp
        other_args.Cg = max(0.0, other_args.Cg)  # non-negative clamp

        old_Cw = other_args.Cw
        other_args.Cw = Cwprev + Cwstep * interp
        other_args.Cw = max(0.0, other_args.Cw)  # non-negative clamp

        # Linearised implicit-Euler coefficients:
        #   newUw = A * newPm - B
        rw_cw_plus_dt_over_2 = speaker.Rw * other_args.Cw + delta_t_over_2
        other_args.A = other_args.Cw / rw_cw_plus_dt_over_2
        other_args.B = (old_Cw * Pcw + Uw * delta_t_over_2) / rw_cw_plus_dt_over_2

        # Solve for Pm via Brent's method.
        min_guess = 0.0
        max_guess = 7840.0  # speaker.Psm * 98

        if state.Pm > 100.0:
            x1 = [min_guess]
            x2 = [max_guess]
            brent_bracket(
                pm_root_function,
                other_args,
                x1,
                x2,
                _BRENT_BRACKET_DEFAULT_FACTOR,
                _BRENT_BRACKET_DEFAULT_NTRY,
            )
            min_guess = x1[0]
            max_guess = x2[0]

        Pm = brent(
            pm_root_function,
            other_args,
            min_guess,
            max_guess,
            _CIRCUIT_TOL,
            _BRENT_DEFAULT_ITMAX,
            _BRENT_DEFAULT_EPS,
        )

        # Update Uw and Pcw from the newly found Pm.
        Uw = _next_uw(Pm, other_args)
        Pcw = Pm - speaker.Rw * Uw

    # ------------------------------------------------------------------
    # Write back final pressure state.
    # ------------------------------------------------------------------
    state.Pm = Pm
    state.Pcw = Pcw

    # ------------------------------------------------------------------
    # Compute derived state quantities (circuit.c lines 303-323).
    # Areas are in mm² (convert back from cm² where needed via *100).
    # ------------------------------------------------------------------
    # agx (mm²): tracheal-adjusted glottal area (circuit.c line 304-306).
    #   agx0_cgsq = ag_cgsq + Pm * Cg * Lg  (areas in cm²)
    #   agx_mmsq  = frame.ag + Pm * Cg * Lg * 100  (back to mm²)
    Cg_safe = 0.0 if state.Cg < 0.0 else state.Cg
    state.agx = frame.ag + (Pm * Cg_safe * speaker.Lg) * 100.0  # CMSQ_TO_MMSQ
    state.agx = max(state.agx, 0.0)

    # agf (mm²): flow glottal area = agx + ap (clamped, circuit.c line 307).
    ap_safe = 0.0 if frame.ap < 0.0 else frame.ap
    state.agf = state.agx + ap_safe

    # Flows (CGS, cm³/s) — circuit.c lines 312-323.
    # Ug: glottal flow.
    state.Ug = _flow_sqrt(2.0 * (_cmwater_to_cgs(frame.ps) - Pm) / _RHO) * _mmsq_to_cmsq(state.agf)

    # Uacx: flow through oral constriction.
    state.Uacx = _flow_sqrt(2.0 * Pm / _RHO) * _mmsq_to_cmsq(state.acx)

    # Un: nasal flow (negative an clamped to zero, 25 Mar 1998 fix).
    state.Un = _flow_sqrt(2.0 * Pm / _RHO) * max(0.0, _mmsq_to_cmsq(frame.an))

    # Uw: wall flow (excluding the ue shunt, circuit.c line 323).
    state.Uw = state.Ug - state.Uacx - state.Un - frame.ue


# Alias under the original C-source name for inventory tests.
SpeechCircuit = speech_circuit

__all__ = [
    "SpeechCircuit",
    "speech_circuit",
]
