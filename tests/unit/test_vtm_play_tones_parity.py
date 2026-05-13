"""C-source parity test for :func:`play_tones` against playtone.c.

Re-parses the C body and asserts:

- ``BOOL PlayTones(...)`` is declared with the seven double parameters
  in the order the Python port mirrors.
- ``RISE_TIME``, ``MAX_TONE_BLOCK``, ``TONE_SYMBOL`` literal values.
- The rise / centre / fall segmentation arithmetic
  (``iTotalSamples``, ``iRiseSamples``, ``iCenterSamples``, the
  signed-shift clamp when the burst is too short).
- The duration-in-frames factor 0.15625.
- The sin-squared rise-window math
  (``Sample = sin(Phase); *pRise++ = Sample * Sample;``).
- The centre-loop ``MAX_TONE_BLOCK`` chunking and ``halting`` poll.
- The fall-loop traverses ``pRiseBuffer`` in reverse (``i--``).
- ``Tone()`` uses ``sin(*pPhase)`` (the non-LOWCOMPUTE branch).

Plus the usual Python-side behavioural checks: a short burst clamps
its rise window, the rendered sample count matches the rise + centre
math, the rise / fall windows are symmetric mirror images, the
halting callback truly stops the centre loop, software volume is
applied multiplicatively, and the ``output_data`` callback receives
the expected segmentation.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.play_tones import (
    MAX_TONE_BLOCK,
    RISE_TIME,
    TONE_SYMBOL,
    TWO_PI_EQUIVALENT,
    play_tones,
    render_tone_burst,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/playtone.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_playtone_c() -> str:
    """Read playtone.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_playtones_body() -> str:
    """Return everything between the opening ``{`` and the closing ``}``.

    Uses a brace-counting scan because the body contains ``#ifdef``
    guards (e.g. ``#ifdef SOFTWARE_VOLUME``) that confuse a regex.
    """
    text = _read_playtone_c()
    # Find the signature line.
    match = re.search(r"BOOL\s+PlayTones\s*\(", text)
    assert match is not None, "PlayTones() signature not found in playtone.c"
    # Skip past the parameter list.
    paren_depth = 1
    idx = match.end()
    while idx < len(text) and paren_depth > 0:
        if text[idx] == "(":
            paren_depth += 1
        elif text[idx] == ")":
            paren_depth -= 1
        idx += 1
    # Skip whitespace until the opening ``{``.
    while idx < len(text) and text[idx] != "{":
        idx += 1
    assert text[idx] == "{", "couldn't find opening brace of PlayTones()"
    start = idx + 1
    # Brace-count to the matching ``}``.
    brace_depth = 1
    idx = start
    while idx < len(text) and brace_depth > 0:
        if text[idx] == "{":
            brace_depth += 1
        elif text[idx] == "}":
            brace_depth -= 1
        idx += 1
    assert brace_depth == 0, "couldn't find closing brace of PlayTones()"
    return text[start : idx - 1]


def _extract_tone_body() -> str:
    """Return the body of the static ``Tone()`` helper."""
    text = _read_playtone_c()
    match = re.search(
        r"static\s+double\s+Tone\s*\(\s*double\s+\w+\s*,\s*double\s*\*\s*\w+\s*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "static Tone() body not found in playtone.c"
    return match.group(1)


# --------------------------------------------------------------------------
# C-source signature / literal-value checks.
# --------------------------------------------------------------------------


def test_signature_takes_seven_doubles() -> None:
    """``BOOL PlayTones(phTTS, Duration, F0, A0, F1, A1, SampleRate)``."""
    text = _read_playtone_c()
    # Multi-line declaration: BOOL PlayTones( LPTTS_HANDLE_T phTTS,
    #   double DurationInMsec, double Freq_0, double Amp_0, double Freq_1,
    #   double Amp_1, double SampleRate )
    sig = re.search(
        r"BOOL\s+PlayTones\s*\(\s*"
        r"LPTTS_HANDLE_T\s+\w+\s*,\s*"
        r"double\s+DurationInMsec\s*,\s*"
        r"double\s+Freq_0\s*,\s*"
        r"double\s+Amp_0\s*,\s*"
        r"double\s+Freq_1\s*,\s*"
        r"double\s+Amp_1\s*,\s*"
        r"double\s+SampleRate\s*\)",
        text,
    )
    assert sig is not None, "PlayTones() signature did not match expected shape"


def test_rise_time_literal() -> None:
    """``#define RISE_TIME 0.002``."""
    text = _read_playtone_c()
    assert re.search(r"#define\s+RISE_TIME\s+0\.002\b", text), (
        "RISE_TIME definition missing or changed"
    )
    assert RISE_TIME == 0.002


def test_max_tone_block_literal() -> None:
    """``#define MAX_TONE_BLOCK 1024`` on the non-UNDER_CE build."""
    text = _read_playtone_c()
    # The non-UNDER_CE branch.
    assert re.search(r"#define\s+MAX_TONE_BLOCK\s+1024\b", text), (
        "MAX_TONE_BLOCK definition missing or changed"
    )
    assert MAX_TONE_BLOCK == 1024


def test_tone_symbol_literal() -> None:
    """``#define TONE_SYMBOL 0x7FFF``."""
    text = _read_playtone_c()
    assert re.search(r"#define\s+TONE_SYMBOL\s+0x7FFF\b", text), (
        "TONE_SYMBOL definition missing or changed"
    )
    assert TONE_SYMBOL == 0x7FFF


def test_two_pi_equivalent_matches_c() -> None:
    """Non-LOWCOMPUTE: ``TWO_PI_EQUIVALENT = 2 * M_PI`` (radians)."""
    text = _read_playtone_c()
    assert re.search(r"#define\s+TWO_PI_EQUIVALENT\s+2\s*\*\s*M_PI\b", text)
    assert abs(TWO_PI_EQUIVALENT - 2.0 * math.pi) < 1e-12


# --------------------------------------------------------------------------
# C-source body math checks.
# --------------------------------------------------------------------------


def test_duration_in_frames_factor() -> None:
    """``dwDurationInFrames = (int)(0.15625 * DurationInMsec)``."""
    body = _extract_playtones_body()
    assert re.search(
        r"dwDurationInFrames\s*=\s*\(int\)\(\s*0\.15625\s*\*\s*DurationInMsec\s*\)",
        body,
    ), "duration-in-frames computation missing or changed"


def test_total_samples_formula() -> None:
    """``iTotalSamples = (int)(0.001 * DurationInMsec * SampleRate)``."""
    body = _extract_playtones_body()
    assert re.search(
        r"iTotalSamples\s*=\s*\(int\)\(\s*0\.001\s*\*\s*DurationInMsec\s*\*\s*SampleRate\s*\)",
        body,
    )


def test_rise_samples_formula() -> None:
    """``iRiseSamples = (int)((double)RISE_TIME * SampleRate)``."""
    body = _extract_playtones_body()
    assert re.search(
        r"iRiseSamples\s*=\s*\(int\)\(\s*\(\s*double\s*\)\s*RISE_TIME\s*\*\s*SampleRate\s*\)",
        body,
    )


def test_center_samples_formula() -> None:
    """``iCenterSamples = iTotalSamples - (iRiseSamples << 1)``."""
    body = _extract_playtones_body()
    assert re.search(
        r"iCenterSamples\s*=\s*iTotalSamples\s*-\s*\(\s*iRiseSamples\s*<<\s*1\s*\)",
        body,
    )


def test_negative_center_clamp_uses_signed_shift() -> None:
    """The ``iCenterSamples < 0`` branch clamps rise via ``>> 1``."""
    body = _extract_playtones_body()
    assert re.search(r"if\s*\(\s*iCenterSamples\s*<\s*0\s*\)", body)
    assert re.search(r"iRiseSamples\s*=\s*iCenterSamples\s*>>\s*1", body)
    assert re.search(r"iCenterSamples\s*=\s*0\s*;", body)


def test_rise_window_is_sin_squared() -> None:
    """The rise table holds ``sin(phase) * sin(phase)``."""
    body = _extract_playtones_body()
    # PhaseIncrement_0 = 0.25 * TWO_PI_EQUIVALENT / (double)iRiseSamples
    assert re.search(
        r"PhaseIncrement_0\s*=\s*0\.25\s*\*\s*TWO_PI_EQUIVALENT\s*/\s*\(\s*double\s*\)\s*iRiseSamples",
        body,
    )
    # Sample = sin(Phase_0);
    assert re.search(r"Sample\s*=\s*sin\s*\(\s*Phase_0\s*\)", body)
    # *pRise++ = Sample * Sample;
    assert re.search(r"\*pRise\+\+\s*=\s*Sample\s*\*\s*Sample", body)


def test_phase_increment_uses_sample_period() -> None:
    """``PhaseIncrement_N = Freq_N * pKsd_t->SamplePeriod * TWO_PI_EQUIVALENT``."""
    body = _extract_playtones_body()
    assert re.search(
        r"PhaseIncrement_0\s*=\s*Freq_0\s*\*\s*pKsd_t->SamplePeriod\s*\*\s*TWO_PI_EQUIVALENT",
        body,
    )
    assert re.search(
        r"PhaseIncrement_1\s*=\s*Freq_1\s*\*\s*pKsd_t->SamplePeriod\s*\*\s*TWO_PI_EQUIVALENT",
        body,
    )


def test_center_loop_chunks_at_max_tone_block() -> None:
    """The centre loop caps each chunk at ``MAX_TONE_BLOCK``."""
    body = _extract_playtones_body()
    assert re.search(r"while\s*\(\(\s*iCenterCount\s*<\s*iCenterSamples", body)
    assert re.search(r"if\s*\(\s*iSynthCount\s*>\s*MAX_TONE_BLOCK\s*\)", body)
    assert re.search(r"iSynthCount\s*=\s*MAX_TONE_BLOCK", body)


def test_center_loop_polls_halting() -> None:
    """The centre loop's while-condition includes ``!pKsd_t->halting``."""
    body = _extract_playtones_body()
    assert re.search(r"!\s*pKsd_t->halting", body), (
        "halting poll missing from centre while-condition"
    )


def test_fall_loop_walks_rise_buffer_in_reverse() -> None:
    """``for (i = iRiseSamples - 1; i >= 0; i--)`` is the fall loop."""
    body = _extract_playtones_body()
    assert re.search(
        r"for\s*\(\s*i\s*=\s*iRiseSamples\s*-\s*1\s*;\s*i\s*>=\s*0\s*;\s*i--",
        body,
    )


def test_output_data_called_with_tone_symbol_and_duration() -> None:
    """First ``OutputData`` carries the duration code; later ones pass 0."""
    body = _extract_playtones_body()
    # First call: TONE_SYMBOL + the dwDurationInFrames-equivalent expression.
    assert re.search(
        r"OutputData\s*\(\s*phTTS\s*,\s*pToneBuffer\s*,\s*iRiseSamples\s*,\s*"
        r"TONE_SYMBOL\s*,\s*\(\s*DWORD\s*\)\s*\(\s*0\.15625\s*\*\s*DurationInMsec\s*\)",
        body,
    ), "rise-segment OutputData call shape did not match"
    # Subsequent calls: duration == 0.
    assert re.search(
        r"OutputData\s*\(\s*phTTS\s*,\s*pToneBuffer\s*,\s*iSynthCount\s*,\s*TONE_SYMBOL\s*,\s*0\s*,\s*0\s*\)",
        body,
    )
    assert re.search(
        r"OutputData\s*\(\s*phTTS\s*,\s*pToneBuffer\s*,\s*iRiseSamples\s*,\s*TONE_SYMBOL\s*,\s*0\s*,\s*0\s*\)",
        body,
    )


def test_software_volume_branch_scales_amplitudes() -> None:
    """``iSwVolume < 0`` scales both amps by ``10 ** (iSwVolume / 10.0)``."""
    body = _extract_playtones_body()
    assert re.search(r"if\s*\(\s*pKsd_t->iSwVolume\s*<\s*0\s*\)", body)
    amp_scale_re = (
        r"Amp_{}\s*\*=\s*pow\s*\(\s*10\s*,"
        r"\s*\(\s*pKsd_t->iSwVolume\s*/\s*10\.0\s*\)\s*\)"
    )
    assert re.search(amp_scale_re.format(0), body)
    assert re.search(amp_scale_re.format(1), body)


def test_static_tone_uses_sin() -> None:
    """``Tone()`` returns ``sin(*pPhase)`` (the non-LOWCOMPUTE branch)."""
    body = _extract_tone_body()
    assert re.search(r"Sample\s*=\s*sin\s*\(\s*\*\s*pPhase\s*\)", body)
    assert re.search(r"\*pPhase\s*\+=\s*PhaseIncrement", body)
    assert re.search(r"if\s*\(\s*\*\s*pPhase\s*>=\s*TWO_PI_EQUIVALENT\s*\)", body)
    assert re.search(r"\*pPhase\s*-=\s*TWO_PI_EQUIVALENT", body)


# --------------------------------------------------------------------------
# Python-side behavioural tests against the rendered samples.
# --------------------------------------------------------------------------


def test_rendered_sample_count_matches_segment_math() -> None:
    """Rendered length == ``2 * rise_samples + center_samples``.

    Pick a sample rate / duration combo that produces a non-trivial
    centre segment (10 ms at 11025 Hz -> 110 samples total, 22 rise,
    22 fall, 66 centre).
    """
    samples = render_tone_burst(
        duration_in_msec=10.0,
        freq_0=697.0,
        amp_0=2000.0,
        freq_1=1209.0,
        amp_1=2000.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    # int(0.001 * 10 * 11025) = 110, int(0.002 * 11025) = 22.
    rise = int(RISE_TIME * 11025.0)
    total = int(0.001 * 10.0 * 11025.0)
    center = total - 2 * rise
    assert len(samples) == 2 * rise + center


def test_short_burst_clamps_rise() -> None:
    """A burst shorter than ``2 * RISE_TIME`` collapses the rise window.

    Pick 1 ms at 11025 Hz: total = 11, rise = 22 -> center = 11 - 44 = -33.
    The C source then sets rise = -33 >> 1 = -17, center = 0. With our
    Python guard for ``rise_samples <= 0``, the rise/fall buffers are
    empty and the burst renders to zero samples.
    """
    samples = render_tone_burst(
        duration_in_msec=1.0,
        freq_0=697.0,
        amp_0=2000.0,
        freq_1=1209.0,
        amp_1=2000.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    assert samples == []


def test_zero_duration_renders_nothing() -> None:
    """Zero duration -> total_samples == 0, rise_samples > 0; center is negative.

    With duration=0, total=0 and rise=22 -> center = -44 -> clamp.
    Same outcome as the short-burst clamp test: empty result.
    """
    samples = render_tone_burst(
        duration_in_msec=0.0,
        freq_0=697.0,
        amp_0=2000.0,
        freq_1=1209.0,
        amp_1=2000.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    assert samples == []


def test_rise_window_is_zero_at_start() -> None:
    """The first rendered sample is zero (rise_buffer[0] == sin(0)**2 == 0)."""
    samples = render_tone_burst(
        duration_in_msec=100.0,
        freq_0=697.0,
        amp_0=2000.0,
        freq_1=0.0,
        amp_1=0.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    assert samples[0] == 0


def test_rise_window_reaches_full_gain_at_boundary() -> None:
    """The sample just past the rise window uses full amplitude.

    The rise table ramps 0..(near-1) over ``rise_samples`` steps, so
    the centre segment kicks in at full gain. Pick a low-frequency
    tone and a short rise so we can spot the transition without
    cancellation between the rise and centre regions.
    """
    sample_rate = 11025.0
    samples = render_tone_burst(
        duration_in_msec=100.0,  # plenty of centre samples
        freq_0=200.0,
        amp_0=10000.0,
        freq_1=0.0,
        amp_1=0.0,
        sample_rate=sample_rate,
        sample_period=1.0 / sample_rate,
    )
    rise = int(RISE_TIME * sample_rate)
    # By the start of the centre, peak amplitude should exceed
    # ``rise_buffer[-1] * amp_0`` (which is < amp_0). The actual peak
    # within the centre approaches amp_0 in magnitude.
    centre_max = max(abs(s) for s in samples[rise : rise + int(sample_rate / 200.0)])
    rise_max = max(abs(s) for s in samples[:rise])
    assert centre_max > rise_max


def test_fall_window_ends_at_zero() -> None:
    """The very last rendered sample uses ``rise_buffer[0] == 0``."""
    samples = render_tone_burst(
        duration_in_msec=100.0,
        freq_0=697.0,
        amp_0=2000.0,
        freq_1=0.0,
        amp_1=0.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    assert samples[-1] == 0


def test_zero_tones_render_silence() -> None:
    """Both amplitudes at zero -> every sample is zero."""
    samples = render_tone_burst(
        duration_in_msec=50.0,
        freq_0=697.0,
        amp_0=0.0,
        freq_1=1209.0,
        amp_1=0.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    assert samples
    assert all(s == 0 for s in samples)


def test_tone_frequency_appears_in_spectrum() -> None:
    """A 1000 Hz tone has positive DFT magnitude at the 1000 Hz bin.

    Use a duration long enough that DFT bins are tightly spaced.
    Compute a single DFT bin at 1000 Hz via the explicit sum (no
    NumPy dependency in this test).
    """
    sample_rate = 11025.0
    samples = render_tone_burst(
        duration_in_msec=200.0,
        freq_0=1000.0,
        amp_0=10000.0,
        freq_1=0.0,
        amp_1=0.0,
        sample_rate=sample_rate,
        sample_period=1.0 / sample_rate,
    )

    # Compute |X(1000)| and a couple of off-target bins for contrast.
    def _bin_mag(freq: float) -> float:
        real = 0.0
        imag = 0.0
        omega = 2.0 * math.pi * freq / sample_rate
        for n, value in enumerate(samples):
            real += value * math.cos(omega * n)
            imag -= value * math.sin(omega * n)
        return math.hypot(real, imag)

    mag_1000 = _bin_mag(1000.0)
    mag_500 = _bin_mag(500.0)
    mag_2000 = _bin_mag(2000.0)
    # Target bin must dominate by a wide margin.
    assert mag_1000 > 10 * mag_500
    assert mag_1000 > 10 * mag_2000


def test_dtmf_pair_has_both_tones() -> None:
    """A 697 + 1209 Hz burst (DTMF '1') shows energy at both bins."""
    sample_rate = 11025.0
    samples = render_tone_burst(
        duration_in_msec=200.0,
        freq_0=697.0,
        amp_0=5000.0,
        freq_1=1209.0,
        amp_1=5000.0,
        sample_rate=sample_rate,
        sample_period=1.0 / sample_rate,
    )

    def _bin_mag(freq: float) -> float:
        real = 0.0
        imag = 0.0
        omega = 2.0 * math.pi * freq / sample_rate
        for n, value in enumerate(samples):
            real += value * math.cos(omega * n)
            imag -= value * math.sin(omega * n)
        return math.hypot(real, imag)

    mag_697 = _bin_mag(697.0)
    mag_1209 = _bin_mag(1209.0)
    mag_900 = _bin_mag(900.0)  # midway between tones, should be small
    assert mag_697 > 5 * mag_900
    assert mag_1209 > 5 * mag_900


def _render_quiet_burst_args() -> dict[str, float]:
    """Shared positional-arg bundle for the software-volume tests."""
    return {
        "duration_in_msec": 100.0,
        "freq_0": 1000.0,
        "amp_0": 20000.0,
        "freq_1": 0.0,
        "amp_1": 0.0,
        "sample_rate": 11025.0,
        "sample_period": 1.0 / 11025.0,
    }


def test_software_volume_scales_amplitude() -> None:
    """``sw_volume_db < 0`` reduces the rendered peak amplitude."""
    args = _render_quiet_burst_args()
    samples_full = render_tone_burst(
        args["duration_in_msec"],
        args["freq_0"],
        args["amp_0"],
        args["freq_1"],
        args["amp_1"],
        args["sample_rate"],
        args["sample_period"],
    )
    samples_quiet = render_tone_burst(
        args["duration_in_msec"],
        args["freq_0"],
        args["amp_0"],
        args["freq_1"],
        args["amp_1"],
        args["sample_rate"],
        args["sample_period"],
        sw_volume_db=-30,
    )
    peak_full = max(abs(s) for s in samples_full)
    peak_quiet = max(abs(s) for s in samples_quiet)
    # -30 dB ≈ factor of 0.001 power, i.e. amplitude factor of ~0.001
    # since the source applies pow(10, dB/10) to amplitude directly.
    assert peak_quiet < peak_full
    assert peak_quiet < peak_full // 100


def test_software_volume_non_negative_leaves_amplitude_unchanged() -> None:
    """``sw_volume_db >= 0`` or ``None`` -> no scaling applied."""
    args = _render_quiet_burst_args()
    base_call = (
        args["duration_in_msec"],
        args["freq_0"],
        args["amp_0"],
        args["freq_1"],
        args["amp_1"],
        args["sample_rate"],
        args["sample_period"],
    )
    samples_none = render_tone_burst(*base_call)
    samples_zero = render_tone_burst(*base_call, sw_volume_db=0)
    samples_positive = render_tone_burst(*base_call, sw_volume_db=10)
    assert samples_none == samples_zero == samples_positive


def test_halting_stops_centre_loop() -> None:
    """A halting callback that fires immediately skips the centre loop.

    Rise + fall still emit (the centre's ``while`` guard is checked
    before each chunk, but the rise/fall loops are unconditional).
    """
    sample_rate = 11025.0
    duration = 100.0
    captured: list[tuple[int, int, int, int]] = []

    def _sink(samples: list[int], count: int, symbol: int, duration_code: int) -> None:
        captured.append((len(samples), count, symbol, duration_code))

    play_tones(
        duration,
        697.0,
        2000.0,
        1209.0,
        2000.0,
        sample_rate,
        1.0 / sample_rate,
        output_data=_sink,
        is_halting=lambda: True,  # halt immediately
    )
    # Expect exactly two OutputData calls: rise + fall, no centre.
    assert len(captured) == 2
    rise = int(RISE_TIME * sample_rate)
    duration_frames = int(0.15625 * duration)
    # Rise call carries the duration code.
    assert captured[0] == (rise, rise, TONE_SYMBOL, duration_frames)
    # Fall call carries duration 0.
    assert captured[1] == (rise, rise, TONE_SYMBOL, 0)


def test_output_data_sees_three_segments_for_short_centre() -> None:
    """Centre fits in one chunk -> rise + centre + fall = three calls."""
    sample_rate = 11025.0
    duration = 50.0  # 550 samples total, 22 rise/fall, 506 centre.
    captured: list[tuple[int, int, int]] = []

    def _sink(samples: list[int], count: int, symbol: int, duration_code: int) -> None:
        _ = samples
        captured.append((count, symbol, duration_code))

    play_tones(
        duration,
        697.0,
        2000.0,
        1209.0,
        2000.0,
        sample_rate,
        1.0 / sample_rate,
        output_data=_sink,
    )
    assert len(captured) == 3
    rise = int(RISE_TIME * sample_rate)
    total = int(0.001 * duration * sample_rate)
    center = total - 2 * rise
    duration_frames = int(0.15625 * duration)
    assert captured[0] == (rise, TONE_SYMBOL, duration_frames)
    assert captured[1] == (center, TONE_SYMBOL, 0)
    assert captured[2] == (rise, TONE_SYMBOL, 0)


def test_output_data_chunks_centre_over_multiple_calls() -> None:
    """Centre > MAX_TONE_BLOCK -> multiple centre OutputData calls."""
    sample_rate = 11025.0
    # Pick a duration that makes centre > MAX_TONE_BLOCK (1024).
    # total = int(0.001 * D * 11025), rise = 22; we want centre = total - 44 > 1024.
    duration = 300.0  # total = 3307, centre = 3307 - 44 = 3263 -> 4 chunks (1024,1024,1024,191).
    captured: list[tuple[int, int, int]] = []

    def _sink(samples: list[int], count: int, symbol: int, duration_code: int) -> None:
        _ = samples
        captured.append((count, symbol, duration_code))

    play_tones(
        duration,
        697.0,
        2000.0,
        1209.0,
        2000.0,
        sample_rate,
        1.0 / sample_rate,
        output_data=_sink,
    )
    rise = int(RISE_TIME * sample_rate)
    total = int(0.001 * duration * sample_rate)
    center = total - 2 * rise
    # Expected: 1 rise + ceil(center / 1024) centre + 1 fall.
    expected_centre_calls = (center + MAX_TONE_BLOCK - 1) // MAX_TONE_BLOCK
    assert len(captured) == 1 + expected_centre_calls + 1

    # Centre chunks are MAX_TONE_BLOCK-sized except possibly the last.
    centre_counts = [c[0] for c in captured[1:-1]]
    assert all(c == MAX_TONE_BLOCK for c in centre_counts[:-1])
    # Last centre chunk is the remainder.
    assert centre_counts[-1] == center - MAX_TONE_BLOCK * (expected_centre_calls - 1)
    # Fall chunk has rise_samples.
    assert captured[-1][0] == rise


def test_returns_false_on_success() -> None:
    """The success-path return value is ``False`` (mirrors C ``FALSE``)."""
    result = play_tones(
        50.0,
        697.0,
        2000.0,
        1209.0,
        2000.0,
        11025.0,
        1.0 / 11025.0,
    )
    assert result is False


def test_sample_values_within_short_range() -> None:
    """All emitted samples fit in 16-bit signed range (-32768..32767)."""
    samples = render_tone_burst(
        duration_in_msec=50.0,
        freq_0=697.0,
        amp_0=20000.0,
        freq_1=1209.0,
        amp_1=12000.0,
        sample_rate=11025.0,
        sample_period=1.0 / 11025.0,
    )
    for s in samples:
        assert -32768 <= s <= 32767, f"sample {s} out of short range"


def test_phase_continuity_across_segments() -> None:
    """A pure 1 Hz tone with continuous phase produces a smooth waveform.

    If the rise/centre/fall segments mishandled phase tracking we'd
    see a visible discontinuity. Test by checking that consecutive
    samples differ by less than the amplitude (i.e. waveform is
    locally smooth) across the rise->centre and centre->fall borders.
    """
    sample_rate = 11025.0
    duration = 30.0  # gives rise=22, total=330, centre=286, fall=22.
    samples = render_tone_burst(
        duration_in_msec=duration,
        freq_0=200.0,  # period = 55 samples at 11025 Hz
        amp_0=10000.0,
        freq_1=0.0,
        amp_1=0.0,
        sample_rate=sample_rate,
        sample_period=1.0 / sample_rate,
    )
    rise = int(RISE_TIME * sample_rate)
    # Adjacent samples differ by < 2 * amp_0 * sin(omega) ≈ amp_0 * omega
    # for small omega; here omega = 2pi*200/11025 ≈ 0.114, so the
    # max step is about 1140. Allow generous slack.
    max_step = max(
        abs(samples[i] - samples[i - 1])
        for i in (rise, rise + 1, len(samples) - rise - 1, len(samples) - rise)
    )
    assert max_step < 3000, f"phase discontinuity at segment boundary: step {max_step}"
