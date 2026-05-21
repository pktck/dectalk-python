"""Nasal pole-zero solver and helpers from nasalf1x.c.

Translated from ``src/dapi/src/hlsyn/nasalf1x.c``.

This module ports the full ``nasalf1x.c`` translation unit — the
top-level ``SetNasals_f1x`` entry point and all its static helpers:

- :func:`set_nasals_f1x` (``SetNasals_f1x``) — top-level dispatcher;
  decides whether the nasal cavity is open and calls the three sub-solvers.
- :func:`nasal_first_formant` (``NasalFirstFormant``) — computes the
  nasal-coupled first formant ``f1x`` and its bandwidth ``b1x``.
- :func:`nasal_pole` (``NasalPole``) — places the nasal pole ``FNP``
  and its bandwidth ``BNP`` via Brent's root-finding method.
- :func:`susceptance_sum` (``SusceptanceSum``) — Brent target function:
  sum of the nasal-branch susceptances ``Bn + Bp + Bm``.
- :func:`finite_bracket_fnp` (``FiniteBracketFNP``) — walks inward from
  ``fn`` and ``fp`` to find a finite bracket for the Brent solver.

The module deliberately re-exports the helpers from :mod:`.nasal_zero`
and :mod:`.compute_fm` (``NasalZero``, ``Compute_fm``,
``InterpolateTable``, ``LinearInterpolate``) so that the hlsyn module
inventory test sees every name from ``nasalf1x.c`` as ported.

Constants from ``hlsyn.h`` used here:

- ``AN_NO_NASAL_BREAKPOINT = -0.0`` -- nasal area threshold below which
  the nasal cavity is considered sealed. The C uses ``-0.0f`` so the
  test is ``frame->an <= -0.0f``, i.e. ``frame->an <= 0`` (IEEE 754:
  ``-0.0 == 0.0``, so any ``an <= 0`` triggers the sealed path).
- ``SPEEDSOUND = 35400.0`` cm/s.
- ``RHO = 0.00114`` g/cm^3.
- ``FLOAT_EPS = 10 * FLT_MIN ≈ 1.175e-37`` -- a near-zero floor for
  division guards.
- ``PI = 3.14159265359`` (C single-precision approximation).
- ``FINITE_OFFSET = 0.1`` -- fractional step used by
  :func:`finite_bracket_fnp` to back away from the singularities.
- ``MAX_FINITE_ITERATIONS = 50``.
- ``FNP_TOL = 1e-5`` -- Brent root tolerance.
- ``ITMAX = 100`` / ``EPS = 3.0e-8`` -- Brent iteration cap / epsilon.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from dectalk.hlsyn.brent import brent
from dectalk.hlsyn.compute_fm import compute_fm
from dectalk.hlsyn.interpolate import interpolate_table, linear_interpolate
from dectalk.hlsyn.nasal_tables import (
    ANFN_TABLE,
    ANFN_TABLE_FNO,
    NASAL_BANDWIDTH,
)
from dectalk.hlsyn.nasal_zero import nasal_zero
from dectalk.ph.hlsyn_structs import TableRow

if TYPE_CHECKING:
    from dectalk.hlsyn.ll_frame_n import LLFrameN
    from dectalk.ph.hl_speaker import HLSpeaker
    from dectalk.ph.hlsyn_structs import HLFrame, HLState

# ---------------------------------------------------------------------------
# Constants (hlsyn.h)
# ---------------------------------------------------------------------------

#: Nasal area threshold below which the nasal cavity is considered sealed.
#: C: ``#define AN_NO_NASAL_BREAKPOINT (-0.0f)``.  In IEEE 754 ``-0.0f == 0.0f``,
#: so ``frame->an <= -0.0f`` is true for ``frame->an <= 0``.
_AN_NO_NASAL_BREAKPOINT: float = 0.0

#: Speed of sound in cm/s.  ``hlsyn.h``: ``#define SPEEDSOUND 35400.f``.
_SPEEDSOUND: float = 35400.0

#: Air density in g/cm^3.  ``hlsyn.h``: ``#define RHO 0.00114f``.
_RHO: float = 0.00114

#: Near-zero floor for division guards.
#: ``hlsyn.h``: ``#define FLOAT_EPS (10.0f * FLT_MIN)``
#: ``FLT_MIN`` (C ``float``) ≈ 1.175494e-38.
_FLOAT_EPS: float = 10.0 * 1.175494e-38

#: Pi (C single-precision value used in ``SusceptanceSum``).
_PI: float = 3.14159265359

#: Fractional step away from the poles in :func:`finite_bracket_fnp`.
#: ``nasalf1x.c``: ``#define FINITE_OFFSET 0.1f``.
_FINITE_OFFSET: float = 0.1

#: Maximum iterations for :func:`finite_bracket_fnp`.
_MAX_FINITE_ITERATIONS: int = 50

#: Return code: bracket successfully found.
_FINITE_BRACKETED: int = 1

#: Return code: bracket not found after max iterations.
_NOT_FINITE_BRACKETED: int = 0

#: Brent root tolerance.  ``nasalf1x.c``: ``#define FNP_TOL 1.0e-5f``.
_FNP_TOL: float = 1.0e-5

#: Brent maximum iterations.  ``nasalf1x.c``: ``#define ITMAX 100``.
_ITMAX: int = 100

#: Brent machine floating-point precision.
#: ``nasalf1x.c``: ``#define EPS 3.0e-8f``.
_EPS: float = 3.0e-8

#: C single-precision ``FLT_EPSILON`` used in the K2-zero guard.
#: ``nasalf1x.c``: ``(1.0 + 2.5 * FLT_EPSILON) * fn``
_C_FLT_EPSILON: float = 1.192093e-07


# ---------------------------------------------------------------------------
# TableRow compatibility helper.
# ---------------------------------------------------------------------------


def _interp_tablerow(table: list[TableRow], x: float) -> float:
    """Piecewise-linear lookup for a ``list[TableRow]`` speaker table.

    The HLSpeaker per-voice tables (``anaTable``, ``anbTable``,
    ``f1cTable``, ``anK2Table``) are stored as ``list[TableRow]``
    with ``.Column1`` / ``.Column2`` attributes. This mirrors
    :func:`~dectalk.hlsyn.interpolate.interpolate_table` but accesses
    ``TableRow`` attributes instead of tuple indices.

    Args:
        table: List of :class:`~dectalk.ph.hlsyn_structs.TableRow` rows.
            ``Column1`` must be strictly increasing.
        x: Input value (``Column1`` axis).

    Returns:
        Interpolated ``Column2`` value (or clamped end-point).
    """
    if table[0].Column1 >= x:
        return table[0].Column2
    if table[-1].Column1 <= x:
        return table[-1].Column2
    for i in range(len(table) - 1):
        x1, y1 = table[i].Column1, table[i].Column2
        x2, y2 = table[i + 1].Column1, table[i + 1].Column2
        if x1 <= x < x2:
            return linear_interpolate(x, x1, y1, x2, y2)
    return table[-1].Column2  # unreachable


# ---------------------------------------------------------------------------
# FNPVars -- internal parameter bag (mirrors the C struct).
# ---------------------------------------------------------------------------


class _FNPVars:
    """Parameter bag for :func:`susceptance_sum`, mirrors ``FNPVars`` in C.

    .. code-block:: c

        typedef struct FNPVarsTag {
            float K1;   /* PharangealArea / (RHO * SPEEDSOUND) */
            float K2;   /* InterpolateTable(anK2Table, an) */
            float fn;   /* nasal-cavity resonance (Hz) */
            float fp;   /* moveable-formant resonance (Hz) */
            float f1c;  /* constriction-modified F1 (Hz) */
        } FNPVars;

    """

    __slots__ = ("f1c", "fn", "fp", "k1", "k2")

    def __init__(
        self,
        k1: float,
        k2: float,
        fn: float,
        fp: float,
        f1c: float,
    ) -> None:
        self.k1 = k1
        self.k2 = k2
        self.fn = fn
        self.fp = fp
        self.f1c = f1c


# ---------------------------------------------------------------------------
# susceptance_sum  (static float SusceptanceSum)
# ---------------------------------------------------------------------------


def susceptance_sum(fnp_guess: float, fnp_vars: object) -> float:
    """Sum of nasal-branch susceptances ``Bn + BpPlusBm`` at ``fnp_guess``.

    Faithful translation of:

    .. code-block:: c

        static float
        SusceptanceSum(float FNPGuess, void *FNPvars0)
        {
            float Bn, BpPlusBm;
            FNPVars* FNPvars = (FNPVars *) FNPvars0;
            Bn = -FNPvars->K2 / (FNPGuess - FNPvars->fn);
            BpPlusBm = (float)(FNPvars->K1 * tan(PI/2. *
                (FNPGuess - FNPvars->f1c) /
                (FNPvars->fp - FNPvars->f1c)));
            return Bn + BpPlusBm;
        }

    Args:
        fnp_guess: Trial nasal pole frequency (Hz).
        fnp_vars: An :class:`_FNPVars` instance holding ``k1``, ``k2``,
            ``fn``, ``fp``, ``f1c``.

    Returns:
        ``Bn + BpPlusBm``.  The Brent solver calls this looking for a
        zero crossing (root = FNP).
    """
    v: _FNPVars = fnp_vars  # type: ignore[assignment]
    bn = -v.k2 / (fnp_guess - v.fn)
    bp_plus_bm = v.k1 * math.tan(_PI / 2.0 * (fnp_guess - v.f1c) / (v.fp - v.f1c))
    return bn + bp_plus_bm


# ---------------------------------------------------------------------------
# finite_bracket_fnp  (static int FiniteBracketFNP)
# ---------------------------------------------------------------------------


def finite_bracket_fnp(
    fnp_vars: _FNPVars,
    f1c: float,
) -> tuple[int, float, float]:
    """Find a finite bracket ``[brac_low, brac_high]`` for the nasal pole.

    Faithful translation of:

    .. code-block:: c

        static int
        FiniteBracketFNP(FNPVars* FNPvars, float f1c,
                         float *Brac_low, float *Brac_high)

    The susceptance function (see :func:`susceptance_sum`) diverges to
    ``-inf`` near ``fn`` (from above) and to ``+inf`` near ``fp`` (from
    below).  This routine finds two finite points ``brac_low < root`` and
    ``root < brac_high`` such that the function evaluates to a negative
    number at ``brac_low`` and a positive number at ``brac_high``.

    It also knows that the root lies above ``fn`` and above ``f1c``.

    Args:
        fnp_vars: Holds ``fn``, ``fp``, ``k1``, ``k2``, ``f1c``.
        f1c: Constriction-modified F1 (Hz) — the lower bound on FNP.

    Returns:
        ``(status, brac_low, brac_high)`` where ``status`` is
        :data:`_FINITE_BRACKETED` (1) on success or
        :data:`_NOT_FINITE_BRACKETED` (0) on failure.
    """
    # Root is above fn and f1c; avoid the singularities at fn and fp.
    if fnp_vars.fn >= f1c:
        brac_low = fnp_vars.fn + _FINITE_OFFSET * (fnp_vars.fp - fnp_vars.fn)
        min_f = fnp_vars.fn
    else:
        min_f = brac_low = f1c

    brac_high = fnp_vars.fn + (1.0 - _FINITE_OFFSET) * (fnp_vars.fp - fnp_vars.fn)
    max_f = fnp_vars.fp

    # Decrease lower endpoint until the function is non-positive there.
    for _ in range(_MAX_FINITE_ITERATIONS):
        if susceptance_sum(brac_low, fnp_vars) <= 0.0:
            break
        brac_low -= (1.0 - _FINITE_OFFSET) * (brac_low - min_f)
    else:
        return _NOT_FINITE_BRACKETED, brac_low, brac_high

    # Increase upper endpoint until the function is non-negative there.
    for _ in range(_MAX_FINITE_ITERATIONS):
        if susceptance_sum(brac_high, fnp_vars) >= 0.0:
            break
        brac_high += (1.0 - _FINITE_OFFSET) * (max_f - brac_high)
    else:
        return _NOT_FINITE_BRACKETED, brac_low, brac_high

    return _FINITE_BRACKETED, brac_low, brac_high


# ---------------------------------------------------------------------------
# Internal bandwidth helper shared by NasalFirstFormant and NasalPole.
# ---------------------------------------------------------------------------


def _bnp_low_f1c_branch(
    an: float,
    temp: float,
    speaker: HLSpeaker,
) -> float:
    """Bandwidth for the ``f1c <= fno`` branch of NasalFirstFormant / NasalPole.

    Shared helper to keep the branch count in each caller below ruff's
    ``PLR0912`` limit.  The caller already computed
    ``temp = B1m + MMSQ_TO_CMSQ(an) * NasalBandwidth``.

    Args:
        an: Nasal area clamped to non-negative (mm^2).
        temp: Upper-plateau bandwidth value (Hz).
        speaker: Speaker definition; reads ``BNP_B1_anLow``,
            ``BNP_B1_anHigh``.

    Returns:
        Bandwidth value in Hz.
    """
    if an <= speaker.BNP_B1_anLow:
        return NASAL_BANDWIDTH
    if an >= speaker.BNP_B1_anHigh:
        return temp
    return linear_interpolate(
        an,
        speaker.BNP_B1_anLow,
        NASAL_BANDWIDTH,
        speaker.BNP_B1_anHigh,
        temp,
    )


# ---------------------------------------------------------------------------
# nasal_first_formant  (static void NasalFirstFormant)
# ---------------------------------------------------------------------------


def nasal_first_formant(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
) -> tuple[float, float]:
    """Return the nasal-coupled first formant ``(f1x, b1x)`` in Hz.

    Faithful translation of:

    .. code-block:: c

        static void
        NasalFirstFormant(HLFrame *frame, HLSpeaker *speaker, HLState *state,
                          float *pf1x, float *pb1x)

    The first formant is shifted by the nasal coupling: when the nasal
    area ``an`` is non-zero the oral first formant ``f1c`` is pulled
    toward the nasal resonance ``fno``.  The shift magnitude depends on
    look-up tables stored in the speaker definition (``anaTable`` for the
    ``f1c >= fno`` branch, ``anbTable`` for ``f1c < fno``).

    Bandwidth ``b1x`` is similarly adjusted: it rises with ``an`` and the
    nasal bandwidth constant.

    Args:
        frame: HL frame; reads ``an``.
        speaker: Speaker definition; reads ``B1m``, ``fno``,
            ``BNP_B1_anLow``, ``BNP_B1_anHigh``, ``anaTable``,
            ``anbTable``, ``f1cTable``.
        state: HL state; reads ``f1c``.

    Returns:
        ``(f1x, b1x)`` -- nasal-coupled F1 and its bandwidth (Hz).
    """
    an = max(0.0, frame.an)

    # --- bandwidth b1x ---
    # From nasals.c (Dave Williams version).
    temp = speaker.B1m + an * 0.01 * NASAL_BANDWIDTH  # MMSQ_TO_CMSQ(an) * NasalBandwidth

    b1x = temp if state.f1c <= speaker.fno else _bnp_low_f1c_branch(an, temp, speaker)

    # --- frequency f1x ---
    # Approximate the susceptances Bn and (Bp + Bm) as straight lines.
    # The slopes come from the speaker look-up tables.
    # Speaker tables are list[TableRow]; use _interp_tablerow.
    ana_table: list[TableRow] = speaker.anaTable  # type: ignore[assignment]
    anb_table: list[TableRow] = speaker.anbTable  # type: ignore[assignment]

    # c = susceptance slope at f1c
    c: float = _interp_tablerow(speaker.f1cTable, state.f1c)  # type: ignore[arg-type]

    if state.f1c >= speaker.fno:
        a: float = _interp_tablerow(ana_table, an)
        if an < ana_table[0].Column1:
            # Extrapolate via hyperbola: a_eff = const/an.
            q_f1c: float = an * c
            q_fno: float = ana_table[0].Column1 * a
        else:
            q_f1c = c
            q_fno = a
    else:
        b: float = _interp_tablerow(anb_table, an)
        if an < anb_table[0].Column1:
            # Linearly extrapolate to b = 0 at an = 0.
            q_f1c = anb_table[0].Column1 * c
            q_fno = an * b
        else:
            q_f1c = c
            q_fno = b

    denom: float = q_f1c + q_fno
    if abs(denom) < _FLOAT_EPS:
        # Guard against zero division (C DEBUG branch calls exit(1) here).
        f1x: float = (state.f1c + speaker.fno) / 2.0
    else:
        f1x = (q_f1c * state.f1c + q_fno * speaker.fno) / denom

    return f1x, b1x


# ---------------------------------------------------------------------------
# nasal_pole  (static void NasalPole)
# ---------------------------------------------------------------------------


def nasal_pole(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
) -> tuple[float, float]:
    """Return the nasal pole ``(FNP, BNP)`` in Hz.

    Faithful translation of:

    .. code-block:: c

        static void
        NasalPole(HLFrame *frame, HLSpeaker *speaker, HLState *state,
                  float *pFNP, float *pBNP)

    The nasal pole frequency is the root of the nasal-branch susceptance
    sum (see :func:`susceptance_sum`).  When ``fp <= fn`` (the movable
    formant lies below the nasal resonance) the two poles bracket the
    pole at their midpoint; otherwise Brent's method is used.

    Args:
        frame: HL frame; reads ``f2``, ``an``.
        speaker: Speaker definition; reads ``B1m``, ``fno``,
            ``BNP_B1_anLow``, ``BNP_B1_anHigh``, ``fp_f2BreakPoint``,
            ``PharangealArea``, ``anK2Table``.
        state: HL state; reads ``f1c``.

    Returns:
        ``(FNP, BNP)`` -- nasal pole centre frequency and bandwidth (Hz).
    """
    an = max(0.0, frame.an)

    # --- bandwidth BNP ---
    temp = speaker.B1m + an * 0.01 * NASAL_BANDWIDTH  # MMSQ_TO_CMSQ(an) * NasalBandwidth

    bnp = _bnp_low_f1c_branch(an, temp, speaker) if state.f1c <= speaker.fno else temp

    # --- frequency FNP ---
    fn = interpolate_table(ANFN_TABLE, an) * (speaker.fno / ANFN_TABLE_FNO)

    if frame.f2 >= speaker.fp_f2BreakPoint:
        fp = 0.00036 * state.f1c * (frame.f2 - speaker.fp_f2BreakPoint) + (
            speaker.fp_f2BreakPoint - 100.0
        )
    else:
        fp = frame.f2 - 100.0

    if fp <= fn:
        # The movable formant is below the nasal resonance; simple midpoint.
        fnp = 0.5 * (fp + fn)
    else:
        # Find the root of the susceptance sum via Brent.
        k1 = speaker.PharangealArea / (_RHO * _SPEEDSOUND)
        k2 = _interp_tablerow(speaker.anK2Table, an)  # type: ignore[arg-type]

        fnp_vars = _FNPVars(k1=k1, k2=k2, fn=fn, fp=fp, f1c=state.f1c)

        # Check whether K2 is (essentially) zero; Bn hyperbola degenerates.
        if susceptance_sum((1.0 + 2.5 * _C_FLT_EPSILON) * fn, fnp_vars) >= 0.0:
            # K2 ≈ 0: the zero collapses onto fn, FNP lies at or above f1c.
            fnp = max(state.f1c, fn)
        else:
            status, brac_low, brac_high = finite_bracket_fnp(fnp_vars, state.f1c)
            if status == _FINITE_BRACKETED:
                fnp = brent(
                    susceptance_sum,
                    fnp_vars,
                    brac_low,
                    brac_high,
                    _FNP_TOL,
                    _ITMAX,
                    _EPS,
                )
            else:
                # Bracket failed: rough midpoint guess (C DEBUG calls exit).
                fnp = 0.5 * (fp + fn)

    return fnp, bnp


# ---------------------------------------------------------------------------
# set_nasals_f1x  (void SetNasals_f1x)
# ---------------------------------------------------------------------------


def set_nasals_f1x(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Set the nasal pole/zero and the nasal-coupled F1 on ``llframe``.

    Faithful translation of:

    .. code-block:: c

        void SetNasals_f1x(HLFrame *frame, HLSpeaker *speaker,
                           HLState *state, LLFrame *llframe)
        {
          if (frame->an <= AN_NO_NASAL_BREAKPOINT) {
              state->f1x = state->f1c;
              state->b1x = speaker->B1m;
              llframe->NFNZ = llframe->NFNP = (short)(speaker->fno + 0.5f);
              llframe->NBNZ = llframe->NBNP = (short)(NasalBandwidth + 0.5f);
          } else {
              float FNZ, BNZ, FNP, BNP;
              NasalFirstFormant(...);
              NasalZero(...);
              NasalPole(...);
              llframe->NFNZ = (short)FNZ;
              ...
          }
        }

    The ``AN_NO_NASAL_BREAKPOINT`` is ``-0.0f`` in C (IEEE 754:
    ``-0.0 == 0.0``), so ``frame->an <= -0.0f`` is true for any
    ``frame->an <= 0``.

    Mutates ``state`` (sets ``f1x``, ``b1x``) and ``llframe``
    (sets ``NFNZ``, ``NBNZ``, ``NFNP``, ``NBNP``) in place.

    Args:
        frame: HL frame; reads ``an`` (and transitively ``f1``, ``f2``,
            ``f3`` via the sub-solvers).
        speaker: Speaker definition; reads various constants and tables.
        state: HL running state; reads ``f1c``, writes ``f1x``/``b1x``.
        llframe: LL frame (N-prefixed variant); writes ``NFNZ``, ``NBNZ``,
            ``NFNP``, ``NBNP``.
    """
    if frame.an <= _AN_NO_NASAL_BREAKPOINT:
        # Nasal cavity is sealed: no nasal pole or zero.
        # Cancel them by setting pole == zero at fno.
        state.f1x = state.f1c
        state.b1x = speaker.B1m
        fno_rounded = int(speaker.fno + 0.5)
        bw_rounded = int(NASAL_BANDWIDTH + 0.5)
        llframe.NFNZ = llframe.NFNP = fno_rounded
        llframe.NBNZ = llframe.NBNP = bw_rounded
    else:
        f1x, b1x = nasal_first_formant(frame, speaker, state)
        fnz, bnz = nasal_zero(frame, speaker, state)
        fnp, bnp = nasal_pole(frame, speaker, state)

        state.f1x = f1x
        state.b1x = b1x
        llframe.NFNZ = int(fnz)
        llframe.NBNZ = int(bnz)
        llframe.NFNP = int(fnp)
        llframe.NBNP = int(bnp)


# ---------------------------------------------------------------------------
# C-name aliases (inventory test requires exact C symbol names).
# ---------------------------------------------------------------------------

# Top-level entry from nasalf1x.c.
SetNasals_f1x = set_nasals_f1x

# Static helpers — also present in hl_stubs.py as no-ops; the inventory
# test checks the Python *module* namespace, not any specific file.
NasalFirstFormant = nasal_first_formant
NasalPole = nasal_pole
SusceptanceSum = susceptance_sum
FiniteBracketFNP = finite_bracket_fnp

# Re-exports from sibling modules so every nasalf1x.c symbol is visible.
# These are imported at module scope above and the inventory test scans
# all Python files in the hlsyn package.
NasalZero = nasal_zero  # re-exported from nasal_zero.py
Compute_fm = compute_fm  # re-exported from compute_fm.py
InterpolateTable = interpolate_table  # re-exported from interpolate.py
LinearInterpolate = linear_interpolate  # re-exported from interpolate.py


__all__ = [
    "Compute_fm",
    "FiniteBracketFNP",
    "InterpolateTable",
    "LinearInterpolate",
    "NasalFirstFormant",
    "NasalPole",
    "NasalZero",
    "SetNasals_f1x",
    "SusceptanceSum",
    "compute_fm",
    "finite_bracket_fnp",
    "interpolate_table",
    "linear_interpolate",
    "nasal_first_formant",
    "nasal_pole",
    "nasal_zero",
    "set_nasals_f1x",
    "susceptance_sum",
]
