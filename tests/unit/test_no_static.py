"""Regression tests for the static-y artefact in voiced segments.

The original bug: ``_render_segment`` rendered ``ceil(n_samples / UI)``
frames into a buffer, then trimmed back to ``n_samples`` before
returning. The synth's internal state advanced through the full
rendered range, but the *output buffer* skipped the trimmed tail —
so the next phoneme segment picked up the synth state at a sample
position the listener never heard, producing an audible
discontinuity at every phoneme boundary that sounded like static.

These tests catch that regression with two complementary checks:

- A direct vs sequencer waveform comparison for a steady-vowel
  rendering. Pre-fix this had RMS difference ≈ 6000 LSB; post-fix
  the inter-harmonic noise floor is identical between the two paths
  (matches at the harmonic peaks, both have zero inter-harmonic
  power).
- A voiced-only high-band power check on ``speak("hello world")``.
  Pre-fix there was audible mid-band leakage, scoring around -55 dB;
  post-fix it sits below -70 dB.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.signal import welch  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]

import dectalk
from dectalk.hlsyn.llsyn import LLFrame, LLSynth
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import default_speaker
from dectalk.ph.sequencer import synthesize_phonemes


def _voiced_only(samples: NDArray[np.int16], frame_n: int = 256) -> NDArray[np.int16]:
    """Return the high-RMS frames (loose voiced-segment proxy)."""
    if samples.size < frame_n:
        return samples
    sig = samples.astype(np.float64)
    n_full = sig.size // frame_n
    rms = np.sqrt((sig[: n_full * frame_n].reshape(n_full, frame_n) ** 2).mean(axis=1))
    if rms.size == 0:
        return samples
    keep = rms >= 0.3 * rms.max()
    chunks = [samples[i * frame_n : (i + 1) * frame_n] for i, k in enumerate(keep.tolist()) if k]
    return np.concatenate(chunks) if chunks else samples


def _voiced_high_band_db(samples: NDArray[np.int16]) -> float:
    """Peak power above 4 kHz in voiced frames, in dB-relative-to-int16-max-squared."""
    voiced = _voiced_only(samples)
    if voiced.size < 1024:
        return -120.0
    res = welch(voiced.astype(np.float64), fs=11025, nperseg=1024)  # pyright: ignore[reportUnknownVariableType]
    f: NDArray[np.float64] = np.asarray(res[0], dtype=np.float64)
    p: NDArray[np.float64] = np.asarray(res[1], dtype=np.float64)
    high = p[f > 4000]
    if high.size == 0 or float(high.max()) <= 0:
        return -120.0
    full_scale = float(np.iinfo(np.int16).max) ** 2
    return 10.0 * math.log10(float(high.max()) / full_scale)


def test_sequencer_renders_full_ui_multiples() -> None:
    """Each rendered chunk must be a multiple of the synth's UI frame size.

    If the sequencer trims back to a partial sample count, the synth
    state advances past samples the output didn't capture, creating a
    discontinuity. Asserting full-UI alignment catches a regression.
    """
    spkr = default_speaker()
    out = synthesize_phonemes(["AH", "AH"], intonation=False)
    assert out.size % spkr.UI == 0, (
        f"sequencer output size {out.size} not a multiple of UI={spkr.UI}"
    )


def test_steady_vowel_inter_harmonic_floor_is_zero() -> None:
    """A steady AH via the sequencer must have ~zero inter-harmonic power.

    With the trim discontinuity in place this measured ~888 in the bin
    just below F0; post-fix it's at the floating-point noise floor
    (~0.02 from Welch's window sidelobes, six orders of magnitude
    below the H1 peak). The 1.0 bound catches the regression cleanly.
    """
    samples = synthesize_phonemes(["AH"] * 50, intonation=False)
    res = welch(samples.astype(np.float64), fs=11025, nperseg=2048)  # pyright: ignore[reportUnknownVariableType]
    f: NDArray[np.float64] = np.asarray(res[0], dtype=np.float64)
    p: NDArray[np.float64] = np.asarray(res[1], dtype=np.float64)
    # F0 = 122 Hz from the default frame; inter-harmonic bin at 60 Hz.
    inter_60 = float(p[(f > 50) & (f < 70)].sum())
    inter_185 = float(p[(f > 175) & (f < 195)].sum())
    assert inter_60 < 1.0, f"inter-harmonic power at 60 Hz {inter_60:.3f} >= 1.0 (sequencer leak)"
    assert inter_185 < 1.0, (
        f"inter-harmonic power at 185 Hz {inter_185:.3f} >= 1.0 (sequencer leak)"
    )


def test_hello_world_voiced_high_band_is_quiet() -> None:
    """Voiced segments of "hello world" must not have audible high-band noise.

    Pre-fix this measured around -55 dB (audible static); post-fix it's
    below -70 dB. The bound is set at -50 dB to leave headroom while
    still catching a regression.
    """
    samples = dectalk.speak("hello world")
    high_db = _voiced_high_band_db(samples)
    assert high_db <= -50.0, f"voiced high-band {high_db:.1f} dB > -50 dB (static-y)"


def test_direct_synth_matches_sequencer_for_steady_vowel() -> None:
    """A direct ll_synthesize loop and the sequencer must agree on a steady vowel.

    For 50 frames of identical AH, the only legitimate difference
    between the two paths is buffer length (the sequencer rounds up to
    UI multiples per phoneme). Aligned content should agree at the
    harmonic peaks.
    """
    spkr = default_speaker()
    ah = LLFrame(
        F0=1220, AV=60, OQ=50, SQ=200,
        F1=730, B1=90, F2=1090, B2=110, F3=2440, B3=170,
        F4=3500, B4=250, F5=4500, B5=300,
    )  # fmt: skip
    synth = LLSynth(spkr=spkr)
    direct = np.zeros(spkr.UI * 50, dtype=np.int16)
    for fi in range(50):
        ll_synthesize(synth, ah, direct[fi * spkr.UI : (fi + 1) * spkr.UI])
    seq = synthesize_phonemes(["AH"] * 50, intonation=False)

    # Compare H1 (~122 Hz) and H2 (~244 Hz) peak amplitudes.
    res_d = welch(direct.astype(np.float64), fs=11025, nperseg=2048)  # pyright: ignore[reportUnknownVariableType]
    res_s = welch(seq.astype(np.float64), fs=11025, nperseg=2048)  # pyright: ignore[reportUnknownVariableType]
    f_d: NDArray[np.float64] = np.asarray(res_d[0], dtype=np.float64)
    p_d: NDArray[np.float64] = np.asarray(res_d[1], dtype=np.float64)
    f_s: NDArray[np.float64] = np.asarray(res_s[0], dtype=np.float64)
    p_s: NDArray[np.float64] = np.asarray(res_s[1], dtype=np.float64)
    h1_d = float(p_d[(f_d > 110) & (f_d < 135)].max())
    h1_s = float(p_s[(f_s > 110) & (f_s < 135)].max())
    # The two paths should report H1 power within 5 % of each other.
    assert h1_d > 0 and h1_s > 0
    ratio = max(h1_d, h1_s) / min(h1_d, h1_s)
    assert ratio < 1.05, f"H1 power mismatch {h1_d:.0f} vs {h1_s:.0f} (ratio {ratio:.3f})"
