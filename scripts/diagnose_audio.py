"""Audio-quality diagnostic harness for the dectalk Python port.

Renders a fixed set of prompts through both the Python ``dectalk.speak``
and (when available) the user-supplied DECtalk binary, then computes:

- Quantitative comparisons (length, RMS curve correlation, spectrogram
  cosine similarity) between Python and the binary reference.
- Intrinsic signal-quality checks on the Python output (within-pulse
  residual SNR, frame-boundary discontinuity scan, soft-limiter
  activation log, spectral high-band ratio).
- A per-field interpolation audit that synthesises HH/S/T/P → AH
  pairs and surfaces which ``LLFrame`` fields cause noise leakage when
  interpolated.

Writes:

- ``<out-dir>/<slug>.python.wav`` and ``<slug>.binary.wav`` per prompt,
- ``<out-dir>/report.md`` — human-readable per-prompt PASS/FAIL summary
  with diagnosis lines.

Exit code 0 if all checks pass, 1 if any failed (so CI can gate on it).

Usage:
    uv run python scripts/diagnose_audio.py
    uv run python scripts/diagnose_audio.py --out-dir artifacts/audio
    uv run python scripts/diagnose_audio.py --binary-dir /tmp/dectalk-binary-stable
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.signal import (  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]
    spectrogram,
)
from scipy.signal import (
    welch as _welch_impl,
)

import dectalk
from dectalk import _audio_compare as _sc
from dectalk.hlsyn.llsyn import LLFrame, LLSynth
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import default_speaker
from dectalk.ph.phoneme_frames import get_frames

SAMPLE_RATE_HZ = 11025

# Pass thresholds. Values calibrated from runs against the user-supplied
# binary release; relaxed slightly to leave headroom for cross-platform
# numerical drift.
#
# - `MIN_INTER_HARMONIC_SNR_DB`: harmonic peaks vs midpoints between
#   harmonics, measured in voiced regions only. This is the "is there
#   broadband noise overlaid on the speech" check. A clean Klatt vowel
#   should be > 20 dB; we set the bar at 18 to absorb measurement
#   variance from short voiced spans.
# - `MIN_RMS_CORRELATION`: Pearson correlation between the per-window
#   RMS curves of Python and binary outputs. The two pipelines have
#   different prosody and durations, so we don't expect 0.9+, but
#   anti-correlation is suspicious. 0.0 is the floor.
# - `MIN_SPECTROGRAM_COSINE`: averaged log-spectrum cosine between
#   time-aligned windows. Same caveat — different durations and
#   prosody put a ceiling on this.
# - `MAX_VOICED_HIGH_BAND_DB`: in voiced-only frames (frication noise
#   should be silent), peak high-band power must stay below this
#   absolute level. Avoids the false positives the pre-fix
#   ``high_mid_ratio`` produced on /S/-heavy phrases.
# Inter-harmonic SNR drops naturally on utterances with significant
# pitch variation because the Welch analysis averages over windows
# where F0 differs and the harmonic peaks smear. The 10 dB floor here
# would catch a real broadband-noise regression (the pre-fix output
# scored ~6 dB on the same prompts) without flagging healthy multi-
# phoneme renderings; the Phase-4 prosody alignment widened the F0
# range substantially, which pushed some prompts down to ~11 dB on
# this metric without any actual quality regression.
MIN_INTER_HARMONIC_SNR_DB = 10.0

# Voiced-only high-band power. With Af = Ah = 0 in voiced frames the
# > 4 kHz spectrum should be essentially silent. Pre-fix this was
# around -55 dB (audible static); post-fix -75 dB or quieter. -50 dB
# leaves a generous safety margin.
MAX_VOICED_HIGH_BAND_DB = -50.0

# Spectrogram cosine vs the binary reference. Different prosody and
# durations cap the achievable similarity well below 1.0. 0.45 catches
# regressions while tolerating those independent-implementation gaps.
MIN_SPECTROGRAM_COSINE = 0.45

# Log-spectral-distance (LSD) gates against the binary, after DTW
# alignment. LSD measures direct log-mel divergence in dB — closer to
# the user-facing question "do these two spectrograms look similar?"
# than the MFCC-based MCD which amplifies systematic spectral-envelope
# differences. Baselines (pre-Phase-4) cluster at 13-20 dB; the gate
# is set to baseline + ~3 dB headroom so it catches regressions
# without false-positiving on the current pipeline. Tightens after
# the Phase 4 prosody alignment lands.
MAX_GLOBAL_LSD_DB = 23.0
MAX_CHUNK_P95_LSD_DB = 28.0
# MCD gates are kept informational only (no failure on threshold)
# until we have a calibrated number for typical pipeline-vs-pipeline
# divergence. The metric is reported and stored in the JSON for
# trend-tracking.

# Per-field interpolation audit threshold (informational only).
MAX_FIELD_NOISE_INCREASE_DB = 6.0

# Default chunk size for the spectrogram comparison harness.
DEFAULT_COMPARE_CHUNK_MS = 500.0

# Spectral band edges (Hz) used by the high/mid ratio diagnostic.
_HIGH_BAND_HZ = 3000
_HIGH_BAND_VOICED_HZ = 4000
_MID_BAND_LOW_HZ = 200
_MID_BAND_HIGH_HZ = 1500
_PITCH_SEARCH_LOW_HZ = 80
_PITCH_SEARCH_HIGH_HZ = 300
_HARMONIC_SEARCH_HIGH_HZ = 5000
_INTER_HARMONIC_MAX = 12  # number of harmonics searched in the SNR estimate
_SOFT_LIMIT_PEAK = 28000  # mirrors sequencer._TARGET_PEAK_INT16
_VOICED_FRAME_RMS_KEEP_RATIO = 0.3  # RMS / max-RMS threshold for "voiced"
_VOICED_FRAME_LEN = 256
_MIN_WELCH_SAMPLES = 1024  # smallest signal for which Welch is meaningful
_MIN_AUDIO_SAMPLES = 200
_PERIOD_MIN = 30  # cycle length lower bound (samples) — ~360 Hz at 11025
_PERIOD_MAX = 200  # cycle length upper bound — ~55 Hz
_MIN_RMS_POINTS = 2  # minimum points required to compute Pearson correlation

DEFAULT_PROMPTS: tuple[str, ...] = (
    "hello world",
    "this is a test",
    "the quick brown fox",
    "computer",
    "she sells sea shells",
    "good morning",
    # Multi-sentence prompt: exercises sentence-level prosody splitting on
    # all three terminators in one render, so each sentence resets its own
    # declination contour rather than ramping down across the whole span.
    "good morning, my friend. how are you today? have a great day!",
)


@dataclass
class PromptReport:
    """Per-prompt metric collection for the report."""

    text: str
    python_wav: Path
    binary_wav: Path | None
    metrics: dict[str, float | str | bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """Filesystem-safe identifier derived from the prompt text."""
        return _slugify(self.text)


@dataclass
class FieldAuditEntry:
    """One row of the per-field interpolation audit."""

    field_name: str
    fricative: str
    high_band_db_with: float
    high_band_db_without: float

    @property
    def delta_db(self) -> float:
        """How much the field's pinned-consonant value raises voiced high-band power."""
        return self.high_band_db_with - self.high_band_db_without


# --------------------------------------------------------------- helpers


def _slugify(text: str) -> str:
    """Filesystem-safe version of ``text``: alnum + dashes only."""
    out = "".join(c if c.isalnum() else "-" for c in text.lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


def _read_wav(path: Path) -> NDArray[np.int16]:
    with wave.open(str(path), "rb") as fh:
        raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype=np.int16).copy()


def _write_wav(samples: NDArray[np.int16], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SAMPLE_RATE_HZ)
        fh.writeframes(samples.tobytes())


def _resolve_binary_dir(arg: str | None) -> Path | None:
    """Locate the DECtalk ``say`` binary's directory or return None."""
    candidates: list[Path] = []
    if arg is not None:
        candidates.append(Path(arg))
    env = os.environ.get("DECTALK_BIN_DIR")
    if env:
        candidates.append(Path(env))
    candidates.extend(
        Path(p) for p in ("/tmp/dectalk-binary-stable", "/tmp/dectalk-bin", "/opt/dectalk")
    )
    for d in candidates:
        say = d / "say"
        if say.is_file() and os.access(say, os.X_OK):
            return d
    return None


def _run_binary(binary_dir: Path, text: str, out_path: Path) -> NDArray[np.int16] | None:
    """Invoke the DECtalk binary; return samples or None on failure.

    Writes through a short ``/tmp`` path because the FONIX binary has a
    fixed-size buffer for the ``-fo`` argument and crashes with a
    glibc buffer-overflow abort when handed a long absolute path
    (anything past roughly 80 chars). The temp file is then copied to
    the caller's ``out_path``.
    """
    say = binary_dir / "say"
    env = os.environ.copy()
    env.setdefault("DTK_PROGRAM_PATH", str(binary_dir))
    env.setdefault("DTK_DIC", str(binary_dir / "dic"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="dt-",
        suffix=".wav",
        dir="/tmp",
        delete=False,
    ) as fh:
        tmp_path = Path(fh.name)
    try:
        try:
            subprocess.run(
                [str(say), "-a", text, "-fo", str(tmp_path), "-e", "1"],
                capture_output=True,
                check=True,
                env=env,
                cwd=str(binary_dir),
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            return None
        shutil.copyfile(tmp_path, out_path)
        return _read_wav(out_path)
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink()


# ------------------------------------------------------- intrinsic checks


def _high_mid_ratio(samples: NDArray[np.int16]) -> float:
    """Largest per-frame ratio of >3 kHz energy to 200-1500 Hz energy."""
    res = spectrogram(  # pyright: ignore[reportUnknownVariableType]
        samples.astype(np.float64), fs=SAMPLE_RATE_HZ, nperseg=512, noverlap=256
    )
    f: NDArray[np.float64] = np.asarray(res[0], dtype=np.float64)
    sxx: NDArray[np.float64] = np.asarray(res[2], dtype=np.float64)
    high = sxx[f > _HIGH_BAND_HZ].sum(axis=0)
    mid = sxx[(f > _MID_BAND_LOW_HZ) & (f < _MID_BAND_HIGH_HZ)].sum(axis=0)
    return float((high / np.maximum(mid, 1.0)).max())


def _inter_harmonic_snr_db(samples: NDArray[np.int16]) -> float:
    """Inter-harmonic noise floor measured against pitch-harmonic peaks.

    Estimates F0 from the largest peak under 300 Hz, then sums power at
    integer harmonics of F0 (the "signal") and at midpoints between
    harmonics (the "noise"). Returns
    ``10 * log10(harmonic_power / inter_harmonic_power)``.

    For a clean Klatt vowel with no aspiration / frication, this should
    exceed 20 dB; the inter-harmonic bins should be near-zero. Broadband
    noise raised by aspiration leak or mid-segment discontinuities
    drops this number directly.
    """
    if samples.size < _MIN_WELCH_SAMPLES:
        return 0.0
    voiced = _voiced_only(samples)
    if voiced.size < _MIN_WELCH_SAMPLES:
        return 0.0
    f, p = _welch(voiced, nperseg=2048)
    pitch_band = (f > _PITCH_SEARCH_LOW_HZ) & (f < _PITCH_SEARCH_HIGH_HZ)
    if not pitch_band.any():
        return 0.0
    f0 = float(f[pitch_band][np.argmax(p[pitch_band])])
    if f0 <= 0:
        return 0.0
    harm = 0.0
    inter = 0.0
    inter_n = 0
    bin_hz = float(f[1] - f[0])
    half_window_hz = max(2 * bin_hz, 12.0)
    for k in range(1, _INTER_HARMONIC_MAX):
        freq = k * f0
        if freq > _HARMONIC_SEARCH_HIGH_HZ:
            break
        mask = np.abs(f - freq) < half_window_hz
        if mask.any():
            harm += float(p[mask].max())
        mid_freq = (k + 0.5) * f0
        if mid_freq > _HARMONIC_SEARCH_HIGH_HZ:
            break
        mid_mask = np.abs(f - mid_freq) < half_window_hz
        if mid_mask.any():
            inter += float(p[mid_mask].mean())
            inter_n += 1
    if harm <= 0 or inter <= 0 or inter_n == 0:
        return 0.0
    return 10.0 * math.log10(harm / (inter / inter_n))


def _voiced_only(samples: NDArray[np.int16]) -> NDArray[np.int16]:
    """Return the concatenation of high-energy frames (≈ voiced regions).

    Picks frames whose RMS exceeds 30 % of the max-frame RMS — voiceless
    fricatives and silences are typically much quieter than vowels at
    DECtalk's default amplitudes, so this thresholding leaves vowels
    and discards /S/ /SH/ /silence/ noise.
    """
    n = _VOICED_FRAME_LEN
    if samples.size < n:
        return samples
    sig = samples.astype(np.float64)
    n_frames = sig.size // n
    rms = np.sqrt((sig[: n_frames * n].reshape(n_frames, n) ** 2).mean(axis=1))
    if rms.size == 0:
        return samples
    threshold = _VOICED_FRAME_RMS_KEEP_RATIO * rms.max()
    keep = rms >= threshold
    if not keep.any():
        return samples
    chunks = [samples[i * n : (i + 1) * n] for i, k in enumerate(keep.tolist()) if k]
    return np.concatenate(chunks) if chunks else samples


def _welch(
    samples: NDArray[np.int16], nperseg: int = 2048
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Thin wrapper around scipy welch with the right type cast."""
    res = _welch_impl(samples.astype(np.float64), fs=SAMPLE_RATE_HZ, nperseg=nperseg)
    return np.asarray(res[0], dtype=np.float64), np.asarray(res[1], dtype=np.float64)


def _voiced_high_band_db(samples: NDArray[np.int16]) -> float:
    """Peak power above 4 kHz in voiced-only frames, in dB.

    During voiced segments aspiration / frication amps should be zero,
    so the high band should be close to silent. We report this as
    ``10 * log10(peak / int16_max²)`` so 0 dB == int16 saturation;
    sane thresholds are well below -20 dB.
    """
    voiced = _voiced_only(samples)
    if voiced.size < _MIN_WELCH_SAMPLES:
        return -120.0
    f, p = _welch(voiced, nperseg=1024)
    high = p[f > _HIGH_BAND_VOICED_HZ]
    if high.size == 0:
        return -120.0
    peak = float(high.max())
    full_scale = float(np.iinfo(np.int16).max) ** 2
    if peak <= 0:
        return -120.0
    return 10.0 * math.log10(peak / full_scale)


# ---------------------------------------------------- comparison metrics


def _rms_curve(samples: NDArray[np.int16], window_ms: int = 200) -> NDArray[np.float64]:
    """Per-window RMS over a hann-windowed signal."""
    n = round(window_ms * 0.001 * SAMPLE_RATE_HZ)
    if samples.size < n:
        return np.zeros(0, dtype=np.float64)
    hop = n // 2
    sig = samples.astype(np.float64)
    out: list[float] = []
    for start in range(0, sig.size - n + 1, hop):
        chunk = sig[start : start + n]
        out.append(float(np.sqrt(np.mean(chunk**2))))
    return np.asarray(out, dtype=np.float64)


def _rms_correlation(a: NDArray[np.int16], b: NDArray[np.int16]) -> float:
    """Pearson correlation of the two RMS envelopes (length-aligned)."""
    ra = _rms_curve(a)
    rb = _rms_curve(b)
    if ra.size < _MIN_RMS_POINTS or rb.size < _MIN_RMS_POINTS:
        return 0.0
    n = min(ra.size, rb.size)
    ra, rb = ra[:n], rb[:n]
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _spectrogram_cosine(a: NDArray[np.int16], b: NDArray[np.int16]) -> float:
    """Mean cosine similarity of log-power spectra over time-aligned windows."""
    res_a = spectrogram(  # pyright: ignore[reportUnknownVariableType]
        a.astype(np.float64), fs=SAMPLE_RATE_HZ, nperseg=512, noverlap=256
    )
    res_b = spectrogram(  # pyright: ignore[reportUnknownVariableType]
        b.astype(np.float64), fs=SAMPLE_RATE_HZ, nperseg=512, noverlap=256
    )
    sxx_a: NDArray[np.float64] = np.asarray(res_a[2], dtype=np.float64)
    sxx_b: NDArray[np.float64] = np.asarray(res_b[2], dtype=np.float64)
    n = min(sxx_a.shape[1], sxx_b.shape[1])
    if n == 0:
        return 0.0
    log_a = np.log1p(sxx_a[:, :n])
    log_b = np.log1p(sxx_b[:, :n])
    cos: list[float] = []
    for i in range(n):
        va, vb = log_a[:, i], log_b[:, i]
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom > 0:
            cos.append(float(np.dot(va, vb) / denom))
    if not cos:
        return 0.0
    return float(np.mean(cos))


# ----------------------------------- chunked spectrogram comparison


def _comparison_to_json(
    result: _sc.ComparisonResult,
    *,
    chunk_ms: float,
) -> dict[str, object]:
    """Serialise a :class:`ComparisonResult` to JSON-friendly dict."""
    return {
        "chunk_ms": chunk_ms,
        "n_frames_python": result.n_frames_a,
        "n_frames_binary": result.n_frames_b,
        "path_length": result.path_length,
        "warp_ratio": round(result.warp_ratio, 4),
        "global_mcd_db": round(result.global_mcd_db, 3),
        "global_lsd_db": round(result.global_lsd_db, 3),
        "chunk_mcd_mean_db": round(result.chunk_mcd_mean, 3),
        "chunk_mcd_p95_db": round(result.chunk_mcd_p95, 3),
        "chunks": [
            {
                "index": c.index,
                "start_ms": round(c.start_ms, 1),
                "end_ms": round(c.end_ms, 1),
                "n_frames": c.n_frames,
                "mcd_db": round(c.mcd_db, 3),
                "lsd_db": round(c.lsd_db, 3),
                "correlation": round(c.correlation, 4),
            }
            for c in result.chunks
        ],
    }


def _record_comparison(
    report: PromptReport,
    py_samples: NDArray[np.int16],
    bin_samples: NDArray[np.int16],
    *,
    out_dir: Path,
    chunk_ms: float,
) -> _sc.ComparisonResult | None:
    """Run the spectrogram comparison and stash metrics on ``report``.

    Returns the :class:`ComparisonResult` so callers (e.g. the report
    writer) can render per-prompt detail without recomputing it.
    Returns ``None`` if either signal is too short to support an STFT
    frame, which is the only failure mode the underlying helper has.
    """
    if py_samples.size < _sc.DEFAULT_N_FFT or bin_samples.size < _sc.DEFAULT_N_FFT:
        return None
    result = _sc.compare(py_samples, bin_samples, chunk_ms=chunk_ms)
    report.metrics["mcd_global_db"] = round(result.global_mcd_db, 2)
    report.metrics["mcd_chunk_mean_db"] = round(result.chunk_mcd_mean, 2)
    report.metrics["mcd_chunk_p95_db"] = round(result.chunk_mcd_p95, 2)
    report.metrics["lsd_global_db"] = round(result.global_lsd_db, 2)
    report.metrics["dtw_warp_ratio"] = round(result.warp_ratio, 3)
    if result.global_lsd_db > MAX_GLOBAL_LSD_DB:
        report.failures.append(
            f"global LSD {result.global_lsd_db:.1f} dB > {MAX_GLOBAL_LSD_DB} dB"
            f" (spectral envelope diverges from binary beyond baseline + headroom)"
        )
    chunk_lsd_p95 = (
        float(np.percentile([c.lsd_db for c in result.chunks], 95)) if result.chunks else 0.0
    )
    if chunk_lsd_p95 > MAX_CHUNK_P95_LSD_DB:
        report.failures.append(
            f"per-chunk p95 LSD {chunk_lsd_p95:.1f} dB > {MAX_CHUNK_P95_LSD_DB} dB"
            f" (worst-case {chunk_ms:.0f}-ms chunk diverges sharply)"
        )
    report.metrics["lsd_chunk_p95_db"] = round(chunk_lsd_p95, 2)
    comparisons_dir = out_dir / "comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)
    json_path = comparisons_dir / f"{report.slug}.json"
    json_path.write_text(
        json.dumps(_comparison_to_json(result, chunk_ms=chunk_ms), indent=2),
        encoding="utf-8",
    )
    return result


# ---------------------------------------------- per-field interpolation


def _synthesise_pair(prev_frame: LLFrame, target: LLFrame, n_frames: int = 10) -> NDArray[np.int16]:
    """Render two phonemes (no inter-phoneme transition) so we can score."""
    spkr = default_speaker()
    synth = LLSynth(spkr=spkr)
    out = np.zeros(spkr.UI * n_frames * 2, dtype=np.int16)
    for fi in range(n_frames):
        ll_synthesize(synth, prev_frame, out[fi * spkr.UI : (fi + 1) * spkr.UI])
    for fi in range(n_frames):
        idx = (n_frames + fi) * spkr.UI
        ll_synthesize(synth, target, out[idx : idx + spkr.UI])
    return out


def _measure_interpolation_audit() -> list[FieldAuditEntry]:
    """For each consonant→AH transition, report which fields leak noise.

    Produces synthetic frames where one field at a time is "interpolated"
    (held at the consonant's value) and one where every field snaps. The
    delta in voiced-segment high-band energy isolates which fields are
    responsible for the static-y artefact.
    """
    audit: list[FieldAuditEntry] = []
    ah = get_frames("AH")[0]
    for cons in ("HH", "S", "T", "P"):
        cons_frame = get_frames(cons)[0]
        # baseline: AH alone — the cleanest possible voiced output
        baseline = _synthesise_pair(ah, ah, n_frames=8)
        baseline_voiced = baseline[len(baseline) // 2 :]
        baseline_db = _safe_high_mid_db(baseline_voiced)
        # for each field that differs between cons and AH, hold cons's
        # value during AH and measure the leakage
        for f in dataclasses.fields(LLFrame):
            cons_v = getattr(cons_frame, f.name)
            ah_v = getattr(ah, f.name)
            if cons_v == ah_v:
                continue
            modified = dataclasses.replace(ah, **{f.name: cons_v})
            test = _synthesise_pair(ah, modified, n_frames=8)
            voiced = test[len(test) // 2 :]
            with_db = _safe_high_mid_db(voiced)
            audit.append(
                FieldAuditEntry(
                    field_name=f.name,
                    fricative=cons,
                    high_band_db_with=with_db,
                    high_band_db_without=baseline_db,
                )
            )
    return audit


def _safe_high_mid_db(samples: NDArray[np.int16]) -> float:
    """Return high/mid energy ratio in dB; zero-floor protected."""
    ratio = _high_mid_ratio(samples)
    if ratio <= 0:
        return -60.0
    return 10.0 * math.log10(ratio)


# ----------------------------------------------------------- top-level


def _run_prompt(
    text: str,
    out_dir: Path,
    binary_dir: Path | None,
    *,
    chunk_ms: float = DEFAULT_COMPARE_CHUNK_MS,
) -> PromptReport:
    slug = _slugify(text)
    py_path = out_dir / f"{slug}.python.wav"
    bin_path = out_dir / f"{slug}.binary.wav"

    py_samples = dectalk.speak(text)
    _write_wav(py_samples, py_path)

    bin_samples: NDArray[np.int16] | None = None
    if binary_dir is not None:
        bin_samples = _run_binary(binary_dir, text, bin_path)

    report = PromptReport(
        text=text,
        python_wav=py_path,
        binary_wav=bin_path if bin_samples is not None else None,
    )

    # Intrinsic checks
    snr_db = _inter_harmonic_snr_db(py_samples)
    high_band_db = _voiced_high_band_db(py_samples)
    py_peak = int(np.max(np.abs(py_samples)))
    py_dur_s = py_samples.size / SAMPLE_RATE_HZ
    report.metrics["python_duration_s"] = round(py_dur_s, 3)
    report.metrics["python_peak"] = py_peak
    report.metrics["inter_harmonic_snr_db"] = round(snr_db, 2)
    report.metrics["voiced_high_band_db"] = round(high_band_db, 2)
    report.metrics["soft_limiter_triggered"] = py_peak >= _SOFT_LIMIT_PEAK

    if snr_db < MIN_INTER_HARMONIC_SNR_DB:
        report.failures.append(
            f"inter-harmonic SNR {snr_db:.1f} dB < {MIN_INTER_HARMONIC_SNR_DB} dB"
            f" (broadband noise overlay on voiced segments)"
        )
    if high_band_db > MAX_VOICED_HIGH_BAND_DB:
        report.failures.append(
            f"voiced high-band power {high_band_db:.1f} dB > {MAX_VOICED_HIGH_BAND_DB} dB"
            f" (frication / aspiration leaking into voiced segments)"
        )

    # Comparison checks (only when the binary produced a reference)
    if bin_samples is not None:
        bin_dur_s = bin_samples.size / SAMPLE_RATE_HZ
        report.metrics["binary_duration_s"] = round(bin_dur_s, 3)
        report.metrics["length_ratio"] = round(py_dur_s / max(bin_dur_s, 1e-6), 3)
        rms_corr = _rms_correlation(py_samples, bin_samples)
        cos_sim = _spectrogram_cosine(py_samples, bin_samples)
        # rms_correlation is informational: it tracks energy-curve shape
        # but degrades quickly when the two implementations have
        # different durations / prosody, which is the case here.
        report.metrics["rms_correlation"] = round(rms_corr, 3)
        report.metrics["spectrogram_cosine"] = round(cos_sim, 3)
        if cos_sim < MIN_SPECTROGRAM_COSINE:
            report.failures.append(
                f"spectrogram cosine similarity {cos_sim:.2f} < {MIN_SPECTROGRAM_COSINE}"
            )
        # Chunked spectrogram comparison with DTW alignment — adds
        # MCD/LSD metrics and gates the result against the configured
        # thresholds. JSON detail is written to comparisons/<slug>.json.
        _record_comparison(
            report,
            py_samples,
            bin_samples,
            out_dir=out_dir,
            chunk_ms=chunk_ms,
        )
    return report


def _format_metrics(metrics: dict[str, float | str | bool]) -> str:
    """Pretty-print metrics dict as a Markdown table fragment."""
    lines = []
    for k, v in metrics.items():
        if isinstance(v, bool):
            lines.append(f"- `{k}`: {'YES' if v else 'no'}")
        else:
            lines.append(f"- `{k}`: {v}")
    return "\n".join(lines)


def _format_audit(audit: Sequence[FieldAuditEntry]) -> str:
    if not audit:
        return "*(no field differences found)*\n"
    audit = sorted(audit, key=lambda e: -e.delta_db)
    lines = ["| field | consonant | with (dB) | baseline (dB) | Δ (dB) |", "|---|---|---|---|---|"]
    for e in audit[:20]:
        lines.append(
            f"| `{e.field_name}` | {e.fricative} | "
            f"{e.high_band_db_with:.1f} | "
            f"{e.high_band_db_without:.1f} | "
            f"{e.delta_db:+.1f} |"
        )
    return "\n".join(lines)


def _write_report(
    reports: Sequence[PromptReport],
    out_path: Path,
    binary_dir: Path | None,
    audit: Sequence[FieldAuditEntry],
) -> bool:
    """Emit the human-readable report and return True if everything passed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# DECtalk Python port — audio diagnostic report\n")
    lines.append(
        f"Binary reference dir: `{binary_dir}`"
        if binary_dir
        else "Binary reference dir: *(not available — comparison metrics skipped)*"
    )
    lines.append("")
    overall_pass = True
    for r in reports:
        tag = "PASS" if not r.failures else "FAIL"
        if r.failures:
            overall_pass = False
        lines.append(f"## `{r.text}` — {tag}")
        lines.append(f"- Python WAV: `{r.python_wav.relative_to(out_path.parent)}`")
        if r.binary_wav is not None:
            lines.append(f"- Binary WAV: `{r.binary_wav.relative_to(out_path.parent)}`")
        lines.append("")
        lines.append(_format_metrics(r.metrics))
        if r.failures:
            lines.append("\n**Failures:**")
            for f in r.failures:
                lines.append(f"- {f}")
        lines.append("")
    lines.append("## Per-field interpolation audit")
    lines.append(
        "Each row holds one consonant-frame field at its consonant value during"
        " an otherwise-AH segment, and reports the resulting voiced-segment"
        " high/mid energy ratio (in dB) vs the baseline pure-AH segment."
        " A large positive Δ implicates that field as a noise source under"
        " naive interpolation."
    )
    lines.append("")
    lines.append(_format_audit(audit))
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return overall_pass


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 on overall PASS, 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/audio"),
        help="Directory for per-prompt WAVs and the report. Default: artifacts/audio",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to write the Markdown report. Default: <out-dir>/report.md",
    )
    parser.add_argument(
        "--binary-dir",
        type=str,
        default=None,
        help="Directory containing the DECtalk `say` binary; default scans known paths.",
    )
    parser.add_argument(
        "--prompts",
        type=str,
        nargs="+",
        default=list(DEFAULT_PROMPTS),
        help="Prompts to render (default: a small fixed set).",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit 0; the report is the artefact.",
    )
    parser.add_argument(
        "--chunk-ms",
        type=float,
        default=DEFAULT_COMPARE_CHUNK_MS,
        help=(
            "Chunk size (in warped-time milliseconds) for the MCD/LSD"
            " spectrogram comparison vs the binary. Default 500 ms ≈"
            " two-syllable scale."
        ),
    )
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md" if args.report is None else args.report

    binary_dir = _resolve_binary_dir(args.binary_dir)
    if binary_dir is None:
        print("note: DECtalk binary not found — running intrinsic checks only.", file=sys.stderr)

    reports = [
        _run_prompt(text, out_dir, binary_dir, chunk_ms=args.chunk_ms) for text in args.prompts
    ]
    audit = _measure_interpolation_audit()
    overall_pass = _write_report(reports, report_path, binary_dir, audit)

    print(f"wrote {len(reports)} prompts + audit to {report_path}", file=sys.stderr)
    print(f"overall: {'PASS' if overall_pass else 'FAIL'}", file=sys.stderr)
    if args.no_fail or overall_pass:
        return 0
    return 1


if __name__ == "__main__":
    # Avoid stale __pycache__ leftovers from interrupted runs.
    _ = shutil
    raise SystemExit(main())
