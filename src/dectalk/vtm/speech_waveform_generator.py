"""Integer Klatt speech-waveform generator from ``vtm1.c``.

Translated from ``src/dapi/src/vtm/vtm1.c`` lines 264-1460.
:func:`speech_waveform_generator` is the **active synthesizer** that
the shipped Linux ``libtts_us.so`` uses to produce PCM samples from
the PH-stage parameter pipe. It is *not* the same code as the
``hlsyn`` SenSyn 2.2 synthesizer ported in ``src/dectalk/hlsyn/``;
the build flags in ``src/dapi/src/vtm/Makefile`` and
``src/dectalkf_klsyn.h`` route ``vtm.c::#include`` through
``vtm1.c`` (when ``VTM1`` is defined, which it is on the active
build) rather than through ``hlsyn`` or ``vtm3.c``.

This port omits the conditional-compile branches that are inactive
on the linux build (none of ``NEW_NOISE, NEW_TILT, NEW_VTM, HLSYN,
HLSYN_NEWPOLE, FAKE_HLSYN, LOWCOMPUTE, COMPRESSION, GERMAN, FP_VTM,
LOWEST, UPGRADES1999, F1_B1_UPGRADE, POSS_FUTURE_FUNCTION, TESTING,
ACI_LICENSE, OUTPERKEN, OLEDECTALK, SAPI5DECTALK, ARM7,
NO_LIMIT_CYCLE_RAMPDOWN, LOW_COST_VERSION, CHANGES_AFTER_V43,
LOWER_YET, MANUAL_TUNE`` are defined in the active build).

The function operates on a :class:`~dectalk.vtm.synth_state.SynthState`
instance — the Python equivalent of the C ``PVTM_T pVtm_t`` per-
handle struct. It reads frame parameters from
``state.parambuff[1..17]`` (the ``OUT_*`` slots) and writes
``state.uiNumberOfSamplesPerFrame`` samples into
``state.iwave[0..uiNumberOfSamplesPerFrame-1]``.

Performance note: pure-Python translation, intended for parity
testing and correctness verification, not as a real-time synthesiser;
production audio should continue to go through ``dectalk._capi.CAPI``.
"""

from __future__ import annotations

# This module is a 1:1 faithful translation of vtm1.c::speech_waveform_generator;
# the C source uses many literal thresholds (40, 263, 95, 16383, ...) and
# `if x > N: x = N` clamp patterns that PLR2004/PLR1730 would flag. The values
# are inherent to the algorithm, not magic constants we should refactor.
# ruff: noqa: PLR0912, PLR0915, PLR1730, PLR2004
from dectalk.include.cmd_codes import PVALUE
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_PH,
    OUT_T0,
    OUT_TLT,
)
from dectalk.vtm.amp_table import amptable
from dectalk.vtm.filters import (
    two_pole_filter,
    two_zero_filter,
    two_zero_filter_2,
)
from dectalk.vtm.frac import frac1mul, frac4mul
from dectalk.vtm.glottal_b0_table import B0
from dectalk.vtm.nasal_zero_tables import azero_tab, bzero_tab, czero_tab
from dectalk.vtm.resonator import (
    SAMPLE_RATE_DECREASE,
    SAMPLE_RATE_INCREASE,
    d2pole_cf123,
    d2pole_pf,
)
from dectalk.vtm.synth_state import NOISEC, RANADD, RANMUL, SynthState

__all__ = ["speech_waveform_generator"]


def _to_s16(x: int) -> int:
    """Sign-extend a 16-bit value into ``[-32768, 32767]``."""
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def _to_s32(x: int) -> int:
    """Sign-extend a 32-bit value into ``[-2**31, 2**31-1]``."""
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def speech_waveform_generator(
    state: SynthState,
    sample_rate: int = 11025,
) -> None:
    """Synthesize one frame of audio into ``state.iwave``.

    Faithful translation of ``vtm1.c::speech_waveform_generator``
    (lines 264-1460). Reads frame parameters from
    ``state.parambuff[1..17]`` and writes
    ``state.uiNumberOfSamplesPerFrame`` samples into
    ``state.iwave[0..uiNumberOfSamplesPerFrame-1]``.

    The body is structured as in the C source:

    1. **Frame-parameter read-in** (lines 366-498). Pulls F1/F2/F3,
       FZ, B1/B2/B3, AV/AP/A2..A6, AB, TILT, T0 from the parambuff,
       applies the speaker-def ``fnscal`` to F1-F3 and the
       sample-rate scale to T0/FZ.
    2. **Per-amplitude amptable lookup** (lines 498-504).
    3. **Speaker-gain scaling** (lines 599-605).
    4. **Parallel R2 / R3 coefficient setup** (lines 612-620).
    5. **Main per-sample loop** (lines 628-1458). For each sample:
       a. Noise generator (LCG + lowpass + Pi-rotated antiresonator).
       b. Voicing waveform (40-kHz oversampled glottal pulse).
       c. Tilt filter.
       d. Voicing + breathiness + aspiration combine.
       e. Cascade tract: nasal-zero -> nasal-pole -> F5 -> F4 -> F3
          -> F2 -> F1.
       f. Parallel tract: noise -> F6 -> F5 -> F4 -> F3 -> F2 -> bypass.
       g. Ramp-down rule (cut signal when AV off and PH = 0).
       h. Clip to int16 and write to ``iwave``.

    The function mutates ``state`` in place — filter delays and
    per-period bookkeeping persist across calls.

    Args:
        state: Per-handle synthesiser state. Mutated in place.
        sample_rate: Output sample rate in Hz; used by
            :func:`d2pole_cf123` for the Fs/2 clamp. Defaults to the
            active build's 11025 Hz.

    Returns:
        None. Output samples are written to ``state.iwave``;
        ``state.uiNumberOfSamplesPerFrame`` indicates how many were
        produced (71 at 11 kHz).
    """
    variabpars = state.parambuff  # alias; OUT_AP is at parambuff[1]

    # Speaker-def-just-loaded silence latch (lines 383-398).
    #
    # The C source latch (vtm1.c:383-398) is ``if(ldspdef>=1){ldspdef++;
    # zero amps;} if(ldspdef>=3) ldspdef=-1;``. Read as ideal integers
    # that trajectory (``1->2->3->-1``) would zero exactly two leading
    # frames -- but ``ldspdef`` is declared ``BOOL`` (vtminst.h:657) and
    # the active linux build's BOOL is ``typedef unsigned char``
    # (``osf/dtmmedefs.h:168``). The ``ldspdef = -1`` therefore stores
    # **255**, so the third frame re-enters the latch (``255 >= 1``),
    # gets its amps zeroed too, and the ``ldspdef++`` wraps 255 -> 0,
    # releasing the latch from frame 3 on. The shipped binary's three
    # silent leading frames are an unsigned-char overflow artifact.
    # Proven in issue #284 by compiling the oracle's own vtm1.c into a
    # standalone packet-fed harness (byte-identical to the oracle WAV,
    # 13845/13845 on ``hello world``) and tracing ``ldspdef`` per
    # frame: 2, 3(->255), 255(->0), 0.
    #
    # The ``>= 4`` threshold below emulates the wrap with a
    # ``1->2->3->4->-1`` trajectory: identical zeroed-frame set (0/1/2)
    # and identical released state (< 1) in every reachable sequence,
    # including mid-stream speaker-definition reloads (which reset
    # ``ldspdef`` to 1 in both forms). On ``hello world`` the oracle's
    # first non-zero sample is 213 (frame 3), byte-matched by this path
    # (#263/#266/#267 measured the same lead empirically; #284's
    # dump-feed control is byte-exact for whole utterances).
    #
    # Note the PH driver in ``api/speak.py::_speak_via_python_full``
    # discards the ``send_pars`` ``initpardelay==0`` seed frame (the
    # #157 leading-bleed fix, keeping the emitted sample count exact);
    # that behaviour is orthogonal to this latch and preserved.
    if state.ldspdef >= 1:
        state.ldspdef += 1
        variabpars[OUT_AV + 1] = 0
        variabpars[OUT_AP + 1] = 0
        variabpars[OUT_A2 + 1] = 0
        variabpars[OUT_A3 + 1] = 0
        variabpars[OUT_A4 + 1] = 0
        variabpars[OUT_A5 + 1] = 0
        variabpars[OUT_A6 + 1] = 0
        variabpars[OUT_AB + 1] = 0
        state.avlin = 0
    if state.ldspdef >= 4:
        state.ldspdef = -1

    # T0 read-in with sample-rate scaling (lines 417-438).
    T0inS4 = variabpars[OUT_T0 + 1]  # noqa: N806
    if state.uiSampleRateChange == SAMPLE_RATE_INCREASE:
        T0inS4 = frac1mul(state.rate_scale, T0inS4) << 1  # noqa: N806
    elif state.uiSampleRateChange == SAMPLE_RATE_DECREASE:
        T0inS4 = frac1mul(state.rate_scale, T0inS4)  # noqa: N806

    # F1 / F2 / F3 read-in with fnscal scaling (lines 446-451). The
    # (4096 - fnscal) >> N additive terms are the C source's "trick to
    # reduce scaling performed if F1inHZ or F2inHZ is relatively low"
    # — they add a small fixed offset compensating for the
    # multiplicative scale's quantisation at low F.
    F1inHZ = variabpars[OUT_F1 + 1]  # noqa: N806
    F1inHZ = frac4mul(F1inHZ, state.fnscal) + _to_s16((4096 - state.fnscal) >> 4)  # noqa: N806
    F2inHZ = variabpars[OUT_F2 + 1]  # noqa: N806
    F2inHZ = frac4mul(F2inHZ, state.fnscal) + _to_s16((4096 - state.fnscal) >> 3)  # noqa: N806
    F3inHZ = variabpars[OUT_F3 + 1]  # noqa: N806
    F3inHZ = frac4mul(F3inHZ, state.fnscal)  # noqa: N806

    # FZ read-in with sample-rate scaling (lines 457-479).
    FZinHZ = variabpars[OUT_FZ + 1]  # noqa: N806
    if state.uiSampleRateChange == SAMPLE_RATE_INCREASE:
        FZinHZ = frac1mul(state.inv_rate_scale, FZinHZ)  # noqa: N806
    elif state.uiSampleRateChange == SAMPLE_RATE_DECREASE:
        FZinHZ = frac1mul(state.inv_rate_scale, FZinHZ) << 1  # noqa: N806

    B1inHZ = variabpars[OUT_B1 + 1]  # noqa: N806
    B2inHZ = variabpars[OUT_B2 + 1]  # noqa: N806
    B3inHZ = variabpars[OUT_B3 + 1]  # noqa: N806
    AVinDB = variabpars[OUT_AV + 1]  # noqa: N806
    APinDB = variabpars[OUT_AP + 1]  # noqa: N806
    A2inDB = variabpars[OUT_A2 + 1]  # noqa: N806
    A3inDB = variabpars[OUT_A3 + 1]  # noqa: N806
    A4inDB = variabpars[OUT_A4 + 1]  # noqa: N806
    A5inDB = variabpars[OUT_A5 + 1]  # noqa: N806
    A6inDB = variabpars[OUT_A6 + 1]  # noqa: N806
    ABinDB = variabpars[OUT_AB + 1]  # noqa: N806
    TILTDB = variabpars[OUT_TLT + 1] - 12  # noqa: N806

    APlin = amptable[APinDB + 10]  # noqa: N806
    r2pg = amptable[A2inDB + 13]
    r3pg = amptable[A3inDB + 10]
    r4pa = amptable[A4inDB + 7]
    r5pa = amptable[A5inDB + 6]
    r6pa = amptable[A6inDB + 5]
    ABlin = amptable[ABinDB + 5]  # noqa: N806

    # Speaker-def gain scaling (lines 599-605).
    APlin = frac4mul(APlin, state.APgain)  # noqa: N806
    r2pg = frac1mul(r2pg, state.AFgain)
    r3pg = frac1mul(r3pg, state.AFgain)
    r4pa = frac1mul(r4pa, state.AFgain)
    r5pa = frac1mul(r5pa, state.AFgain)
    r6pa = frac1mul(r6pa, state.AFgain)
    ABlin = frac4mul(ABlin, state.AFgain)  # noqa: N806

    # Parallel R2 / R3 coefficient setup (lines 608-620).
    b2p = 210
    r2pa, r2pb, r2pc = d2pole_pf(state.inv_rate_scale, state.uiSampleRateChange, F2inHZ, b2p, r2pg)
    b3p = 280
    r3pa, r3pb, r3pc = d2pole_pf(state.inv_rate_scale, state.uiSampleRateChange, F3inHZ, b3p, r3pg)

    # MAIN LOOP (lines 628-1458).
    for ns in range(state.uiNumberOfSamplesPerFrame):
        # Noise generator (lines 636-647).
        state.randomx = _to_s16(state.randomx * RANMUL + RANADD)
        noise = state.randomx >> 2
        noise += frac1mul(24574, state.nolast)
        noise = _to_s16(noise)
        state.nolast = noise

        # Pi-rotated antiresonator on the noise (line 661).
        noise, state.ablas1, state.ablas2 = two_zero_filter_2(
            noise, state.ablas1, state.ablas2, state.noiseb, NOISEC
        )

        # Amplitude-modulate noise (lines 669-670).
        if state.nper < state.nmod:
            noise >>= 1

        # 4x oversampled voicing-waveform loop (lines 682-1082).
        # Pre-bind `voice` so pyright sees a definitely-assigned name
        # after the loop (the inner body always writes it).
        voice: int = 0
        for _nsr4 in range(4):
            # Glottal pulse generator (lines 695-767).
            if state.nper > (state.T0 - state.nopen):
                # Open phase: at**2 - bt**3.
                state.a = _to_s16(state.a - state.b)
                state.voice0 = _to_s16(state.voice0 + (state.a >> 4))
                state.avlind = state.avlin  # Delay AV change.
            else:
                # Closed phase: voice0 = 0 (line 763; NEW_VTM disabled).
                state.voice0 = 0

            # Voicing scaling (line 785; !CHANGES_AFTER_V43 branch).
            voice = frac4mul(state.voice0, state.avgain)

            # Per-period pitch-synchronous updates (lines 795-1063).
            if state.nper == state.T0:
                state.nper = 0
                state.avlin = amptable[AVinDB + 4]
                # T0 reset (line 815; !LOWCOMPUTE branch).
                state.T0 = T0inS4
                state.T0 += frac4mul(state.t0jitr, state.T0)
                state.t0jitr = -state.t0jitr  # Alternating jitter sign.

                # aturb1 = Aturb << 2 (line 832; !CHANGES_AFTER_V43).
                state.aturb1 = state.Aturb << 2

                # F1 minimum (line 835).
                if F1inHZ < 250:
                    F1inHZ = 250  # noqa: N806

                # Tilt decay setup (lines 842-868).
                if state.uiSampleRateChange == SAMPLE_RATE_INCREASE:
                    state.decay = 1094 * _to_s32(TILTDB)
                elif state.uiSampleRateChange == SAMPLE_RATE_DECREASE:
                    state.decay = 1073 * _to_s32(TILTDB)
                else:  # NO_SAMPLE_RATE_CHANGE
                    state.decay = 1094 * _to_s32(TILTDB)
                if state.decay >= 0:
                    state.one_minus_decay = 32767 - state.decay
                else:
                    state.one_minus_decay = 32767

                # Noise-modulation threshold (lines 876-879).
                state.nmod = 0
                if state.avlin > 0:
                    state.nmod = state.T0 >> 1

                # nopen calculation (lines 915-944; !LOWCOMPUTE,
                # !UPGRADES1999 — only the bottom line 915 runs).
                state.nopen = frac1mul(state.k1, state.T0) + state.k2
                state.nopen += TILTDB << 2  # Lengthen if TILT high.
                if state.nopen < 40:
                    state.nopen = 40
                elif state.nopen > 263:
                    state.nopen = 263
                if state.nopen >= (state.T0 * 3) >> 2:
                    state.nopen = (state.T0 * 3) >> 2

                # Glottal-pulse a/b reset (lines 955-981; !LOWCOMPUTE).
                state.b = B0[state.nopen - 40]
                state.temp = state.b + 1
                if state.nopen > 95:
                    state.temp = _to_s32(state.temp) * state.nopen
                    state.a = frac1mul(10923, state.temp)
                else:
                    state.temp = frac1mul(10923, state.temp)
                    state.a = _to_s32(state.temp) * state.nopen

                # Per-period cascade resonator coefficient updates
                # (lines 993-1004; !NEW_VTM).
                state.R3ca, state.r3cb, state.r3cc = d2pole_cf123(
                    sample_rate,
                    state.inv_rate_scale,
                    state.uiSampleRateChange,
                    F3inHZ,
                    B3inHZ,
                    state.r3cg,
                )
                state.R2ca, state.r2cb, state.r2cc = d2pole_cf123(
                    sample_rate,
                    state.inv_rate_scale,
                    state.uiSampleRateChange,
                    F2inHZ,
                    B2inHZ,
                    state.r2cg,
                )
                state.R1ca, state.r1cb, state.r1cc = d2pole_cf123(
                    sample_rate,
                    state.inv_rate_scale,
                    state.uiSampleRateChange,
                    F1inHZ,
                    B1inHZ,
                    state.r1cg,
                )
                if state.R1ca > 16383:
                    state.R1ca = 16383
                state.R1ca = state.R1ca << 1

                # Nasal-zero table lookup (lines 1031-1040;
                # !NEW_VTM, PC_SAMPLE_RATE == 11025).
                state.temp = (FZinHZ >> 3) - 31
                if state.temp > 34:
                    state.temp = 34
                if state.temp < 0:
                    state.temp = 0  # Defensive; C lookup would underflow.
                state.rnza = azero_tab[state.temp]
                state.rnzb = bzero_tab[state.temp]
                state.rnzc = czero_tab[state.temp]
            # End per-period update.

            # Downsampling low-pass filter (lines 1077-1081).
            state.rlpd1, state.rlpd2 = two_pole_filter(
                voice,
                state.rlpd1,
                state.rlpd2,
                state.rlpa,
                state.rlpb,
                state.rlpc,
            )
            voice = state.rlpd1
            state.nper += 1
        # End inner nsr4 loop.

        # Tilt filter (lines 1108-1110).
        voice = frac1mul(state.one_minus_decay, voice) + frac1mul(state.decay, state.vlast)
        state.vlast = voice

        # Breathiness (line 1128; !CHANGES_AFTER_V43, !NEW_VTM).
        voice += frac1mul(state.aturb1, noise)

        # AV final scaling (line 1137; !CHANGES_AFTER_V43).
        voice = frac4mul(state.avlind, voice)

        # Aspiration (line 1148).
        voice += frac1mul(APlin, noise)

        # CASCADE VOCAL TRACT (lines 1168-1241) ----------------------
        # Nasal antiresonator.
        rnzout, state.rnzd1, state.rnzd2 = two_zero_filter(
            voice,
            state.rnzd1,
            state.rnzd2,
            state.rnza,
            state.rnzb,
            state.rnzc,
        )
        # Nasal pole.
        state.rnpd1, state.rnpd2 = two_pole_filter(
            rnzout,
            state.rnpd1,
            state.rnpd2,
            state.rnpa,
            state.rnpb,
            state.rnpc,
        )
        # Fifth cascade.
        if sample_rate > 9500:
            state.r5cd1, state.r5cd2 = two_pole_filter(
                state.rnpd1,
                state.r5cd1,
                state.r5cd2,
                state.R5ca,
                state.R5cb,
                state.R5cc,
            )
        else:
            state.r5cd1 = frac4mul(state.R5ca, state.rnpd1) >> 1
        # Fourth cascade.
        state.r4cd1, state.r4cd2 = two_pole_filter(
            state.r5cd1,
            state.r4cd1,
            state.r4cd2,
            state.R4ca,
            state.R4cb,
            state.R4cc,
        )
        # Third cascade.
        state.r3cd1, state.r3cd2 = two_pole_filter(
            state.r4cd1,
            state.r3cd1,
            state.r3cd2,
            state.R3ca,
            state.r3cb,
            state.r3cc,
        )
        # Second cascade.
        state.r2cd1, state.r2cd2 = two_pole_filter(
            state.r3cd1,
            state.r2cd1,
            state.r2cd2,
            state.R2ca,
            state.r2cb,
            state.r2cc,
        )
        # First cascade.
        state.r1cd1, state.r1cd2 = two_pole_filter(
            state.r2cd1,
            state.r1cd1,
            state.r1cd2,
            state.R1ca,
            state.r1cb,
            state.r1cc,
        )
        out = state.r1cd1

        # PARALLEL VOCAL TRACT (lines 1263-1311) ---------------------
        # Sixth parallel.
        state.r6pd1, state.r6pd2 = two_pole_filter(
            noise, state.r6pd1, state.r6pd2, r6pa, state.r6pb, state.r6pc
        )
        out = state.r6pd1 - out
        # Fifth parallel.
        if sample_rate > 9600:
            state.r5pd1, state.r5pd2 = two_pole_filter(
                noise, state.r5pd1, state.r5pd2, r5pa, state.R5pb, state.r5pc
            )
        else:
            state.r5pd1 = 0
        out = state.r5pd1 - out
        # Fourth parallel.
        state.r4pd1, state.r4pd2 = two_pole_filter(
            noise, state.r4pd1, state.r4pd2, r4pa, state.R4pb, state.r4pc
        )
        out = state.r4pd1 - out
        # Third parallel.
        state.r3pd1, state.r3pd2 = two_pole_filter(
            noise, state.r3pd1, state.r3pd2, r3pa, r3pb, r3pc
        )
        out = state.r3pd1 - out
        # Second parallel.
        state.r2pd1, state.r2pd2 = two_pole_filter(
            noise, state.r2pd1, state.r2pd2, r2pa, r2pb, r2pc
        )
        out = state.r2pd1 - out
        # Bypass path.
        about = frac1mul(ABlin, noise)
        out = about - out

        # Limit-cycle ramp-down (lines 1318-1327;
        # !NO_LIMIT_CYCLE_RAMPDOWN).
        if state.avlind == 0 and (variabpars[OUT_PH + 1] & PVALUE) == 0:
            state.rampdown += 4
            if state.rampdown >= 4096:
                state.rampdown = 4096
            if state.rampdown >= 0:
                out = frac4mul(out, 4096 - state.rampdown)
        else:
            state.rampdown = 0

        # Clip + write (lines 1387-1391; !COMPRESSION).
        if out > 16383:
            out = 16383
        elif out < -16384:
            out = -16384
        state.iwave[ns] = out << 1
