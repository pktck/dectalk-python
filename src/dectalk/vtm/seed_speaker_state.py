"""Seed a :class:`SynthState` with the full speaker / sample-rate context.

The C ``read_speaker_definition`` (``vtm1.c`` lines 1469-1903) and
``SetSampleRate`` (lines 1984-2076) are the two bring-up entries that
populate every field ``speech_waveform_generator`` reads. This module
collapses both into a single helper, :func:`seed_speaker_state`, so the
alternative vtm1 synth path in :mod:`dectalk.api.speak` can produce
audio from an :class:`SpdChip` + sample-rate pair without re-implementing
the full PH/VTM dispatch flow.

The Python helper omits the few sub-features the active linux build
doesn't compile in (``CHANGES_AFTER_V43``, ``COMPRESSION``, ``NEW_VTM``,
``HLSYN``, ``LOWCOMPUTE``, ``FP_VTM``, ``MANUAL_TUNE``, ``UPGRADES1999``,
``LOW_COST_VERSION``, ``TESTING``) -- the field set follows the active
``#ifdef`` slice through ``vtm1.c``.

Tests live in :mod:`tests.unit.test_vtm_seed_speaker_state_parity`,
asserting the C-side constants this Python port relies on still hold.
"""

from __future__ import annotations

from dectalk.ph.spdef_chip import SpdChip
from dectalk.vtm.amp_table import amptable
from dectalk.vtm.frac import frac1mul
from dectalk.vtm.resonator import (
    NO_SAMPLE_RATE_CHANGE,
    SAMPLE_RATE_DECREASE,
    SAMPLE_RATE_INCREASE,
    d2pole_cf45,
    d2pole_pf,
)
from dectalk.vtm.synth_state import SynthState

# 11 kHz target sample rate -- the only path the active linux build
# routes audio through (see ``dectalkf_klsyn.h`` ``PC_SAMPLE_RATE``).
PC_SAMPLE_RATE: int = 11025

# 8 kHz mu-law sample rate (``samprate.h`` line 12, ``MULAW_SAMPLE_RATE``).
MULAW_SAMPLE_RATE: int = 8000

# Q15 rate scalers at 8 kHz (``vtm1.c::SetSampleRate`` lines 2058-2059).
# rate_scale = 0.8 in Q15, inv_rate_scale = 1.25 in Q14. The 11 kHz
# values (18063 / 29722) are computed from the C formulae below rather
# than hard-coded, so PC_SAMPLE_RATE changes flow through automatically.
_RATE_SCALE_8000: int = 26214
_INV_RATE_SCALE_8000: int = 20480

# Hard-coded constants from ``vtm1.c::read_speaker_definition`` body.
_NASAL_FNP_FIXED: int = 290  # line 1635: fixed nasal pole frequency
_NASAL_BNP_FIXED: int = 70  # line 1637: fixed nasal pole bandwidth
_LOWPASS_FLP_11K: int = 948  # line 1674 (PC_SAMPLE_RATE == 11025 branch)
_LOWPASS_BLP_11K: int = 615  # line 1675
_LOWPASS_FLP_8K: int = 698  # line 1685 (SAMPLE_RATE_DECREASE branch)
_LOWPASS_BLP_8K: int = 453  # line 1686
_LOWPASS_FLP_DEFAULT: int = 860  # line 1693 (NO_SAMPLE_RATE_CHANGE default)
_LOWPASS_BLP_DEFAULT: int = 558  # line 1694
_LOWPASS_RLPG: int = 2400  # line 1680: Q4.12 -> 0.5859375
_PARALLEL_B4P: int = 400  # line 1725
_PARALLEL_B5P: int = 500  # line 1734
_R6PB_AT_11K: int = -5702  # line 1759
_R6PC_AT_11K: int = -1995  # line 1760
_NOISEB_INCREASE: int = -2913  # lines 1582 / 1598 (Q4.12 -> -0.711...)
_NOISEB_DECREASE: int = -1873  # line 1590 (Q4.12 -> -0.457...)


def _classify_sample_rate(sample_rate: int) -> int:
    """Return the ``uiSampleRateChange`` enum for ``sample_rate``.

    Mirrors the ``if/else`` tree in ``vtm1.c::SetSampleRate`` lines
    2003-2065. PC_SAMPLE_RATE (11025) gives ``SAMPLE_RATE_INCREASE``
    on the active linux build (the ``#if PC_SAMPLE_RATE == 10000``
    branch sets NO_SAMPLE_RATE_CHANGE, but is not the configured one).
    MULAW_SAMPLE_RATE (8000) gives ``SAMPLE_RATE_DECREASE``. Anything
    else falls back to ``NO_SAMPLE_RATE_CHANGE``.
    """
    if sample_rate == PC_SAMPLE_RATE:
        return SAMPLE_RATE_INCREASE
    if sample_rate == MULAW_SAMPLE_RATE:
        return SAMPLE_RATE_DECREASE
    return NO_SAMPLE_RATE_CHANGE


# ruff: noqa: PLR0915  -- this function intentionally inlines the whole
# vtm1.c::read_speaker_definition body for direct readability; splitting
# into helpers would obscure the line-by-line C correspondence.
def seed_speaker_state(
    state: SynthState,
    spd_chip: SpdChip,
    *,
    sample_rate: int = PC_SAMPLE_RATE,
) -> None:
    """Seed ``state`` with the speaker-definition + sample-rate context.

    Mirrors the bring-up sequence ``vtm.c`` actually runs at the start
    of every utterance: ``SetSampleRate(handle, 11025)`` followed by
    ``read_speaker_definition(handle)``. Both functions mutate the
    handle's ``pVTMThreadData`` struct (the Python equivalent is
    :class:`SynthState`).

    Args:
        state: Per-handle :class:`SynthState`. Mutated in place.
        spd_chip: A :class:`~dectalk.vtm.spd_chip.SpdChip` instance. The
            object is duck-typed; only the ``r4cb``/``r4cc``/``r5cb``/
            ``r5cc``/``r4pb``/``r5pb``/``r5ca``/``r4ca``/``r3ca``/
            ``r2ca``/``r1ca``/``nopen1``/``nopen2``/``aturb``/
            ``fnscale``/``afgain``/``rnpgain``/``azgain``/``apgain``/
            ``t0jit`` attributes are read.
        sample_rate: Output sample rate in Hz. ``PC_SAMPLE_RATE`` (11025)
            and ``MULAW_SAMPLE_RATE`` (8000) take the
            ``SAMPLE_RATE_INCREASE`` / ``SAMPLE_RATE_DECREASE`` branches
            of ``SetSampleRate`` respectively. Anything else falls into
            the ``NO_SAMPLE_RATE_CHANGE`` branch, which mirrors the C
            ``else`` arm and leaves ``rate_scale`` /
            ``uiNumberOfSamplesPerFrame`` at their dataclass defaults.

    Returns:
        None. ``state`` is updated in place.
    """
    # --- SetSampleRate (vtm1.c lines 1986-2069) --------------------------
    # The C function uses pKsd_t->uiSampleRate for the formulae. The
    # Python equivalent stores the float ``SampleRate`` on ``state``.
    state.SampleRate = float(sample_rate)
    rate_change = _classify_sample_rate(sample_rate)
    state.uiSampleRateChange = rate_change

    if sample_rate == PC_SAMPLE_RATE:
        # vtm1.c lines 2003-2046: the PC_SAMPLE_RATE branch. Note the
        # ``+5000`` / ``+10000/2`` rounding mirrors the C integer math.
        state.bEightKHz = False
        # The active linux build defines PC_SAMPLE_RATE == 11025, so the
        # ``#if PC_SAMPLE_RATE == 10000`` arm is not the configured one
        # and we always emit SAMPLE_RATE_INCREASE (set above).
        # rate_scale = round((1<<14) * sample_rate / 10000)
        state.rate_scale = (((1 << 14) * sample_rate) + 5000) // 10000
        # inv_rate_scale = round((1<<15) * 10000 / sample_rate)
        state.inv_rate_scale = ((1 << 15) * 10000 + sample_rate // 2) // sample_rate
        state.uiNumberOfSamplesPerFrame = ((sample_rate * 64) + 5000) // 10000
    elif sample_rate == MULAW_SAMPLE_RATE:
        # vtm1.c lines 2049-2061: the MULAW_SAMPLE_RATE branch.
        state.bEightKHz = True
        state.rate_scale = _RATE_SCALE_8000
        state.inv_rate_scale = _INV_RATE_SCALE_8000
        state.uiNumberOfSamplesPerFrame = 51
    # else: NO_SAMPLE_RATE_CHANGE — vtm1.c lines 2063-2065 leave
    # rate_scale / inv_rate_scale / uiNumberOfSamplesPerFrame untouched.
    # The dataclass defaults (11 kHz values) carry through, matching
    # the C behaviour of running whatever was last loaded.

    # --- read_speaker_definition zero-init (lines 1503-1554) -------------
    state.ldspdef = 1  # flag: just loaded a speaker def (eab 10/96)
    # Filter delays are already zero from SynthState() defaults; reset
    # them explicitly to mirror the C body in case the caller re-uses
    # an existing state across speaker switches.
    for field in (
        "r2pd1",
        "r2pd2",
        "r3pd1",
        "r3pd2",
        "r4pd1",
        "r4pd2",
        "r5pd1",
        "r5pd2",
        "r6pd1",
        "r6pd2",
        "r1cd1",
        "r1cd2",
        "r2cd1",
        "r2cd2",
        "r3cd1",
        "r3cd2",
        "r4cd1",
        "r4cd2",
        "r5cd1",
        "r5cd2",
        "rnpd1",
        "rnpd2",
        "rnzd1",
        "rnzd2",
        "rlpd1",
        "rlpd2",
        "ablas1",
        "ablas2",
        "vlast",
        "one_minus_decay",
        "avlind",
        "voice0",
        "rampdown",
    ):
        setattr(state, field, 0)

    # --- Noise filter coefficients (lines 1578-1607) ----------------------
    # SAMPLE_RATE_DECREASE → -1873; INCREASE / NO_SAMPLE_RATE_CHANGE → -2913.
    if rate_change == SAMPLE_RATE_DECREASE:
        state.noiseb = _NOISEB_DECREASE
    else:
        state.noiseb = _NOISEB_INCREASE

    # --- Parallel 6th formant (lines 1759-1760) --------------------------
    state.r6pb = _R6PB_AT_11K
    state.r6pc = _R6PC_AT_11K

    # --- Nasal-pole resonator (lines 1635-1663) --------------------------
    rnpa, rnpb, rnpc = d2pole_pf(
        state.inv_rate_scale,
        state.uiSampleRateChange,
        _NASAL_FNP_FIXED,
        _NASAL_BNP_FIXED,
        0,
    )
    state.rnpa = rnpa
    state.rnpb = rnpb
    state.rnpc = rnpc

    # --- Down-sampling low-pass filter (lines 1669-1699) -----------------
    # Per-rate flp/blp constants; rlpg is invariant.
    if rate_change == SAMPLE_RATE_INCREASE:
        # PC_SAMPLE_RATE == 11025 branch: hard-coded 948/615 (= 860 *
        # 1.1025 / 558 * 1.1025).
        flp = _LOWPASS_FLP_11K
        blp = _LOWPASS_BLP_11K
    elif rate_change == SAMPLE_RATE_DECREASE:
        flp = _LOWPASS_FLP_8K
        blp = _LOWPASS_BLP_8K
    else:
        flp = _LOWPASS_FLP_DEFAULT
        blp = _LOWPASS_BLP_DEFAULT
    rlpa, rlpb, rlpc = d2pole_pf(
        state.inv_rate_scale,
        state.uiSampleRateChange,
        flp,
        blp,
        _LOWPASS_RLPG,
    )
    state.rlpa = rlpa
    state.rlpb = rlpb
    state.rlpc = rlpc

    # --- Cascade F4 (lines 1706-1709) ------------------------------------
    f4c = int(spd_chip.r4cc)
    b4c = int(spd_chip.r4cb)
    _r4ca_unused, state.R4cb, state.R4cc = d2pole_cf45(
        state.inv_rate_scale, state.uiSampleRateChange, f4c, b4c, 0
    )

    # --- Cascade F5 (lines 1715-1718) ------------------------------------
    f5c = int(spd_chip.r5cc)
    b5c = int(spd_chip.r5cb)
    _r5ca_unused, state.R5cb, state.R5cc = d2pole_cf45(
        state.inv_rate_scale, state.uiSampleRateChange, f5c, b5c, 0
    )

    # --- Parallel F4 (lines 1724-1727) -----------------------------------
    f4p = int(spd_chip.r4pb)  # SPDEF F7 -- frequency despite the "pb" name
    b4p = _PARALLEL_B4P
    _r4pa_unused, state.R4pb, state.r4pc = d2pole_pf(
        state.inv_rate_scale, state.uiSampleRateChange, f4p, b4p, 0
    )

    # --- Parallel F5 (lines 1733-1736) -----------------------------------
    f5p = int(spd_chip.r5pb)  # SPDEF F8 -- frequency
    b5p = _PARALLEL_B5P
    _r5pa_unused, state.R5pb, state.r5pc = d2pole_pf(
        state.inv_rate_scale, state.uiSampleRateChange, f5p, b5p, 0
    )

    # --- Jitter parameter (lines 1780-1804) ------------------------------
    t0jit = int(spd_chip.t0jit)
    state.t0jitr = t0jit  # initial sign branch: t0jitr starts at 0 (>= 0)
    # Rate-scaling switch: INCREASE takes the half-step << 1 path
    # (Q14 → Q15); DECREASE keeps the half-step (Q15 → Q15);
    # NO_SAMPLE_RATE_CHANGE leaves the value alone.
    if rate_change == SAMPLE_RATE_INCREASE:
        state.t0jitr = frac1mul(state.rate_scale, state.t0jitr) << 1
    elif rate_change == SAMPLE_RATE_DECREASE:
        state.t0jitr = frac1mul(state.rate_scale, state.t0jitr)

    # --- Cascade resonator gains (lines 1811-1824) -----------------------
    state.R5ca = amptable[int(spd_chip.r5ca)]
    state.R4ca = amptable[int(spd_chip.r4ca)]
    state.r3cg = amptable[int(spd_chip.r3ca)]
    state.r2cg = amptable[int(spd_chip.r2ca)]
    state.r1cg = amptable[int(spd_chip.r1ca)]

    # --- Glottal-open-phase constants (lines 1831-1832) ------------------
    state.k1 = int(spd_chip.nopen1)
    state.k2 = int(spd_chip.nopen2)

    # --- Breathiness (lines 1838-1845) -----------------------------------
    state.Aturb = amptable[int(spd_chip.aturb)]

    # --- Formant scale factor (line 1855) --------------------------------
    state.fnscal = int(spd_chip.fnscale)

    # --- Source-relative gains (lines 1861-1893) -------------------------
    state.AFgain = amptable[int(spd_chip.afgain)]
    state.rnpa = amptable[int(spd_chip.rnpgain)]
    state.avgain = amptable[int(spd_chip.azgain)]
    state.APgain = amptable[int(spd_chip.apgain)]
    state.SpeakerGain = int(spd_chip.osgain)


__all__ = ["MULAW_SAMPLE_RATE", "PC_SAMPLE_RATE", "seed_speaker_state"]
