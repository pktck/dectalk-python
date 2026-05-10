"""Spectrogram-based audio comparison utilities.

Provides pure-function building blocks used by
:mod:`scripts.diagnose_audio` and the parity tests to measure how
close two synthesized audio signals are without requiring sample-level
parity. The intended use is "Python port vs FONIX binary on the same
prompt": the two outputs have different durations and slightly
different prosody, so a raw chunk-by-chunk waveform comparison is
dominated by timing drift rather than acoustic similarity.

The pipeline is:

1. ``log_mel_spectrogram`` — STFT + mel filterbank + dB scaling, using
   only :mod:`numpy` and :mod:`scipy.signal` (no librosa dependency).
2. ``dtw_align`` — band-constrained dynamic time warping on log-mel
   frames; reports the warp path and per-step cost so duration
   differences don't pollute the metrics.
3. ``chunk_metrics`` — slices the warped pair into fixed-duration
   chunks (default 500 ms in *warped* time) and reports
   mel-cepstral-distortion (MCD), log-spectral distance (LSD), and
   spectral correlation per chunk.

All functions are deterministic, allocation-light, and operate on
``int16`` mono PCM (the format produced by the synthesizer and the
binary). The DTW implementation uses an O(N·band·M) cost matrix; with
the default 20 % Sakoe-Chiba band this is roughly linear in the
longer signal's frame count for our prompt lengths.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from scipy.fft import dct  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]

# ---------------------------------------------------------------------------
# Defaults — calibrated for 11025 Hz mono int16 (the DECtalk native rate).
# ---------------------------------------------------------------------------

DEFAULT_SAMPLE_RATE_HZ: Final[int] = 11025
DEFAULT_N_FFT: Final[int] = 512  # ~46 ms window
DEFAULT_HOP: Final[int] = 128  # ~12 ms hop
DEFAULT_N_MELS: Final[int] = 64
DEFAULT_FMIN_HZ: Final[float] = 80.0
DEFAULT_FMAX_HZ: Final[float] = 5500.0
# Number of MFCC coefficients used for MCD. Standard practice keeps
# coefficients 1..K and drops coefficient 0 (overall energy).
DEFAULT_MFCC_COEFS: Final[int] = 13
# DTW Sakoe-Chiba band fraction. 0.20 = path may stray ±20 % of the
# longer-axis length from the diagonal; tighter would forbid valid
# warps when prosody differs by ~30 %, looser admits pathological ones.
DEFAULT_DTW_BAND: Final[float] = 0.20
# Floor for ``log10(0)`` and similar edge cases. Chosen so
# ``20 * log10(_LOG_FLOOR) = -200 dB`` ≈ "silence".
_LOG_FLOOR: Final[float] = 1e-10
# DTW predecessor codes used by `dtw_align` while filling the cost
# matrix and again on backtrack. Plain ints so the int8 ndarray storage
# stays compact.
_PRED_MATCH: Final[int] = 0  # diagonal step: (i-1, j-1)
_PRED_DELETION: Final[int] = 1  # vertical step: (i-1, j)
_PRED_INSERTION: Final[int] = 2  # horizontal step: (i, j-1)

# Standard MCD assumes MFCCs computed from ``ln(mel)``. Our log-mel
# spectrogram is in dB (``20 * log10(mel)``), so cepstral diffs come
# out a factor of ``20 / ln(10)`` larger. The standard scale of
# ``(10/ln(10)) * sqrt(2)`` collapses to ``sqrt(2)/2`` after
# multiplying by ``ln(10)/20`` to undo the log-base, leaving values
# directly comparable to literature MCD numbers (typically 4-10 dB
# for "similar" TTS pairs, > 10 dB for "perceptibly different").
_MCD_SCALE: Final[float] = math.sqrt(2.0) / 2.0


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChunkMetric:
    """Per-chunk acoustic-similarity metrics computed on warped frames.

    Attributes:
        index: 0-based chunk index in warped time.
        start_ms: Warped-time start of the chunk in milliseconds.
        end_ms: Warped-time end of the chunk in milliseconds.
        n_frames: Number of warped-path frames covered by the chunk.
        mcd_db: Mel-cepstral distortion in dB. ~6.5 dB is the
            literature threshold for human-perceptible difference;
            < 4 dB is "very close".
        lsd_db: Log-spectral distance in dB on log-mel frames.
            Cross-check for ``mcd_db`` since MCD operates on a DCT of
            log-mel and may mask formant-position errors that LSD
            captures.
        correlation: Pearson correlation between flattened log-mel
            chunks in [-1, 1]. Direction-invariant similarity.
    """

    index: int
    start_ms: float
    end_ms: float
    n_frames: int
    mcd_db: float
    lsd_db: float
    correlation: float


@dataclass(frozen=True)
class ComparisonResult:
    """Aggregate result of a Python-vs-binary spectrogram comparison.

    Attributes:
        n_frames_a: Pre-warp frame count of the first signal.
        n_frames_b: Pre-warp frame count of the second signal.
        path_length: Number of points in the DTW warp path.
        warp_ratio: ``path_length / max(n_frames_a, n_frames_b)``. A
            value near 1.0 means the two signals are similarly paced;
            > 1.25 indicates significant duration drift that DTW
            absorbed.
        global_mcd_db: MCD computed over the full warped path.
        global_lsd_db: LSD computed over the full warped path.
        chunks: Per-chunk metrics from :func:`chunk_metrics`.
    """

    n_frames_a: int
    n_frames_b: int
    path_length: int
    warp_ratio: float
    global_mcd_db: float
    global_lsd_db: float
    chunks: list[ChunkMetric]

    @property
    def chunk_mcd_mean(self) -> float:
        """Mean of per-chunk MCD in dB; 0.0 when there are no chunks."""
        if not self.chunks:
            return 0.0
        return float(np.mean([c.mcd_db for c in self.chunks]))

    @property
    def chunk_mcd_p95(self) -> float:
        """95th percentile of per-chunk MCD in dB; 0.0 when no chunks."""
        if not self.chunks:
            return 0.0
        return float(np.percentile([c.mcd_db for c in self.chunks], 95))


# ---------------------------------------------------------------------------
# Mel filterbank + log-mel spectrogram
# ---------------------------------------------------------------------------


def _hz_to_mel(hz: NDArray[np.float64] | float) -> NDArray[np.float64] | float:
    """HTK-style mel transform of a frequency in Hz."""
    return 2595.0 * np.log10(1.0 + np.asarray(hz, dtype=np.float64) / 700.0)


def _mel_to_hz(mel: NDArray[np.float64]) -> NDArray[np.float64]:
    """Inverse HTK-style mel transform back to Hz."""
    return 700.0 * (np.power(10.0, np.asarray(mel, dtype=np.float64) / 2595.0) - 1.0)


def mel_filterbank(
    *,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    n_fft: int = DEFAULT_N_FFT,
    n_mels: int = DEFAULT_N_MELS,
    fmin_hz: float = DEFAULT_FMIN_HZ,
    fmax_hz: float = DEFAULT_FMAX_HZ,
) -> NDArray[np.float64]:
    """Build a triangular mel filterbank matrix.

    Args:
        sample_rate_hz: Sampling rate of the input audio, in Hz.
        n_fft: FFT size; the filterbank columns match ``n_fft // 2 + 1``
            real-FFT bins.
        n_mels: Number of triangular mel filters.
        fmin_hz: Lowest mel-filter center frequency, in Hz.
        fmax_hz: Highest mel-filter center frequency, in Hz.

    Returns:
        A ``(n_mels, n_fft // 2 + 1)`` filterbank matrix; right-multiply
        a magnitude spectrum by it to project onto the mel scale.
    """
    n_bins = n_fft // 2 + 1
    fmin_mel = float(_hz_to_mel(fmin_hz))
    fmax_mel = float(_hz_to_mel(fmax_hz))
    # n_mels + 2 mel points define n_mels triangles (each triangle uses
    # three consecutive points: left edge, peak, right edge).
    mel_points = np.linspace(fmin_mel, fmax_mel, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    # Map Hz to FFT bin indices.
    bin_points = np.floor((n_fft + 1) * hz_points / sample_rate_hz).astype(np.int64)
    bin_points = np.clip(bin_points, 0, n_bins - 1)
    fb = np.zeros((n_mels, n_bins), dtype=np.float64)
    for m in range(1, n_mels + 1):
        left, center, right = bin_points[m - 1], bin_points[m], bin_points[m + 1]
        if center == left:
            center = left + 1
        if right == center:
            right = center + 1
        if center >= n_bins:
            break
        right = min(right, n_bins - 1)
        for k in range(left, center):
            fb[m - 1, k] = (k - left) / max(center - left, 1)
        for k in range(center, right + 1):
            fb[m - 1, k] = (right - k) / max(right - center, 1)
    return fb


def _stft_magnitude(
    samples: NDArray[np.float64],
    *,
    n_fft: int,
    hop: int,
) -> NDArray[np.float64]:
    """Magnitude spectrogram via a hand-rolled Hann-windowed STFT.

    Avoids :func:`scipy.signal.stft` to keep type-stub headaches off
    pyright strict.
    """
    if samples.size < n_fft:
        # Pad with zeros so we always produce at least one frame.
        padded = np.zeros(n_fft, dtype=np.float64)
        padded[: samples.size] = samples
        samples = padded
    n_frames = 1 + (samples.size - n_fft) // hop
    window = np.hanning(n_fft).astype(np.float64)
    out = np.empty((n_frames, n_fft // 2 + 1), dtype=np.float64)
    for i in range(n_frames):
        start = i * hop
        frame = samples[start : start + n_fft] * window
        spec = np.fft.rfft(frame, n=n_fft)
        out[i] = np.abs(spec)
    return out


def log_mel_spectrogram(
    samples: NDArray[np.int16] | NDArray[np.float64],
    *,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
    n_mels: int = DEFAULT_N_MELS,
    fmin_hz: float = DEFAULT_FMIN_HZ,
    fmax_hz: float = DEFAULT_FMAX_HZ,
) -> NDArray[np.float64]:
    """Compute a log-magnitude mel spectrogram in dB.

    Args:
        samples: Mono PCM audio. ``int16`` is rescaled to ``float64``
            in ``[-1, 1]``; ``float64`` is used as-is (no normalisation
            applied, so callers should pass already-scaled audio).
        sample_rate_hz: Sample rate of ``samples``, in Hz.
        n_fft: FFT length per frame.
        hop: Hop length between consecutive frames.
        n_mels: Mel filterbank size.
        fmin_hz: Lowest mel-filter center frequency, in Hz.
        fmax_hz: Highest mel-filter center frequency, in Hz.

    Returns:
        Array of shape ``(n_frames, n_mels)`` in dB. Values below the
        floor of ``20 * log10(_LOG_FLOOR) = -200 dB`` are clamped.
    """
    if samples.dtype == np.int16:
        signal = samples.astype(np.float64) / 32768.0
    else:
        signal = np.asarray(samples, dtype=np.float64)
    mag = _stft_magnitude(signal, n_fft=n_fft, hop=hop)
    fb = mel_filterbank(
        sample_rate_hz=sample_rate_hz,
        n_fft=n_fft,
        n_mels=n_mels,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    mel = mag @ fb.T  # (n_frames, n_mels)
    return 20.0 * np.log10(np.maximum(mel, _LOG_FLOOR))


# ---------------------------------------------------------------------------
# DTW alignment
# ---------------------------------------------------------------------------


def _frame_l2(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Pairwise Euclidean distance between rows of ``a`` and ``b``."""
    # Broadcast trick: ‖a_i - b_j‖ via expanded squared-norm.
    a2 = np.sum(a * a, axis=1, keepdims=True)  # (n_a, 1)
    b2 = np.sum(b * b, axis=1, keepdims=True).T  # (1, n_b)
    cross = a @ b.T  # (n_a, n_b)
    sq = np.maximum(a2 + b2 - 2.0 * cross, 0.0)
    return np.sqrt(sq)


def dtw_align(  # noqa: PLR0912 — DTW recursion intrinsically has 3 predecessor branches plus backtracking
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
    *,
    band: float = DEFAULT_DTW_BAND,
) -> tuple[list[tuple[int, int]], float]:
    """Band-constrained DTW alignment between two log-mel spectrograms.

    Uses the classic 3-step recursion (insertion / deletion / match)
    with a Sakoe-Chiba band that forbids paths straying more than
    ``band * max(n_a, n_b)`` cells from the diagonal. The cost matrix
    is filled with ``np.inf`` outside the band so `np.argmin` picks a
    feasible predecessor.

    Args:
        log_mel_a: First spectrogram, shape ``(n_a, n_mels)``.
        log_mel_b: Second spectrogram, shape ``(n_b, n_mels)``.
        band: Band radius as a fraction of the longer-axis length.
            ``0.0`` would pin the path to the diagonal (only valid
            when ``n_a == n_b``).

    Returns:
        A tuple ``(path, mean_cost)`` where ``path`` is a list of
        ``(i, j)`` index pairs from ``(0, 0)`` to
        ``(n_a - 1, n_b - 1)`` (inclusive), and ``mean_cost`` is the
        total alignment cost divided by the path length.

    Raises:
        ValueError: If either spectrogram is empty or ``band < 0``.
    """
    n_a, n_b = log_mel_a.shape[0], log_mel_b.shape[0]
    if n_a == 0 or n_b == 0:
        raise ValueError("dtw_align: empty input spectrogram")
    if band < 0.0:
        raise ValueError("dtw_align: band must be non-negative")

    # Normalised diagonal slope (n_b moves per n_a step) so the band
    # check stays sane when the two axes have different lengths.
    radius = max(int(band * max(n_a, n_b)), 1)
    distances = _frame_l2(log_mel_a, log_mel_b)
    cost = np.full((n_a, n_b), np.inf, dtype=np.float64)
    cost[0, 0] = distances[0, 0]
    pred = np.full((n_a, n_b), -1, dtype=np.int8)
    for i in range(n_a):
        # Sakoe-Chiba band: cells with |j - i * (n_b / n_a)| > radius
        # are infeasible. We compute the diagonal-slope projected
        # column for this row.
        center = round(i * (n_b - 1) / max(n_a - 1, 1))
        j_lo = max(0, center - radius)
        j_hi = min(n_b - 1, center + radius)
        for j in range(j_lo, j_hi + 1):
            if i == 0 and j == 0:
                continue
            best = np.inf
            best_pred = -1
            if i > 0 and j > 0 and cost[i - 1, j - 1] < best:
                best = cost[i - 1, j - 1]
                best_pred = _PRED_MATCH
            if i > 0 and cost[i - 1, j] < best:
                best = cost[i - 1, j]
                best_pred = _PRED_DELETION
            if j > 0 and cost[i, j - 1] < best:
                best = cost[i, j - 1]
                best_pred = _PRED_INSERTION
            if best_pred == -1:
                continue
            cost[i, j] = best + distances[i, j]
            pred[i, j] = best_pred

    if not math.isfinite(cost[n_a - 1, n_b - 1]):
        # Band too tight to reach the corner — widen and retry once.
        # This guards against degenerate prompts where the prosody
        # drift exceeds the configured band.
        return dtw_align(log_mel_a, log_mel_b, band=min(0.5, band * 2.0))

    # Predecessor codes (match `_PREDS` above): 0 = diagonal,
    # 1 = vertical (deletion), 2 = horizontal (insertion).
    path: list[tuple[int, int]] = []
    i, j = n_a - 1, n_b - 1
    while True:
        path.append((i, j))
        if i == 0 and j == 0:
            break
        p = pred[i, j]
        if p == _PRED_MATCH:
            i, j = i - 1, j - 1
        elif p == _PRED_DELETION:
            i = i - 1
        elif p == _PRED_INSERTION:
            j = j - 1
        else:  # pragma: no cover — defended by the band-widen retry above
            break
    path.reverse()
    mean_cost = float(cost[n_a - 1, n_b - 1] / len(path))
    return path, mean_cost


# ---------------------------------------------------------------------------
# Distance metrics
# ---------------------------------------------------------------------------


def log_mel_to_mfcc(
    log_mel: NDArray[np.float64],
    *,
    n_coefs: int = DEFAULT_MFCC_COEFS,
) -> NDArray[np.float64]:
    """Compute MFCCs from a log-mel spectrogram via DCT-II.

    Args:
        log_mel: Log-mel spectrogram, shape ``(n_frames, n_mels)``.
        n_coefs: Number of cepstral coefficients to return; coefficient
            0 (overall energy) is included so callers can drop or keep
            it as their MCD convention dictates.

    Returns:
        Array of shape ``(n_frames, n_coefs)`` with cepstral
        coefficients along axis 1.
    """
    full: NDArray[np.float64] = np.asarray(
        dct(log_mel, type=2, norm="ortho", axis=1),
        dtype=np.float64,
    )
    return full[:, :n_coefs]


def mcd_db(
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
    *,
    n_coefs: int = DEFAULT_MFCC_COEFS,
) -> float:
    """Mel-cepstral distortion in dB between two equal-length log-mel arrays.

    The two inputs must already be aligned (same number of frames). For
    DTW-aligned signals, pass the warped slices.

    Args:
        log_mel_a: First aligned log-mel spectrogram.
        log_mel_b: Second aligned log-mel spectrogram.
        n_coefs: Number of cepstral coefficients used; coefficient 0
            (overall energy) is dropped per MCD convention.

    Returns:
        Mean MCD across frames, in dB. Returns 0.0 for empty input.

    Raises:
        ValueError: If the two spectrograms have different shapes.
    """
    if log_mel_a.shape != log_mel_b.shape:
        raise ValueError(f"mcd_db: shape mismatch {log_mel_a.shape} vs {log_mel_b.shape}")
    if log_mel_a.size == 0:
        return 0.0
    mfcc_a = log_mel_to_mfcc(log_mel_a, n_coefs=n_coefs)[:, 1:]
    mfcc_b = log_mel_to_mfcc(log_mel_b, n_coefs=n_coefs)[:, 1:]
    diff: NDArray[np.float64] = mfcc_a - mfcc_b
    per_frame: NDArray[np.float64] = _MCD_SCALE * np.sqrt(np.sum(diff * diff, axis=1))
    return float(np.mean(per_frame))


def lsd_db(
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
) -> float:
    """Log-spectral distance in dB between two equal-length log-mel arrays.

    Args:
        log_mel_a: First aligned log-mel spectrogram.
        log_mel_b: Second aligned log-mel spectrogram.

    Returns:
        Mean per-frame log-spectral distance in dB.

    Raises:
        ValueError: If the two spectrograms have different shapes.
    """
    if log_mel_a.shape != log_mel_b.shape:
        raise ValueError(f"lsd_db: shape mismatch {log_mel_a.shape} vs {log_mel_b.shape}")
    if log_mel_a.size == 0:
        return 0.0
    diff: NDArray[np.float64] = log_mel_a - log_mel_b
    # Mean across mel axis then across frames; sqrt of mean-square gives
    # an RMS-style distance in dB units.
    per_frame: NDArray[np.float64] = np.sqrt(np.mean(diff * diff, axis=1))
    return float(np.mean(per_frame))


def correlation(
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
) -> float:
    """Pearson correlation between flattened log-mel arrays in [-1, 1].

    Args:
        log_mel_a: First aligned log-mel spectrogram.
        log_mel_b: Second aligned log-mel spectrogram.

    Returns:
        Pearson correlation; 0.0 when either input is constant.
    """
    if log_mel_a.size == 0 or log_mel_b.size == 0:
        return 0.0
    flat_a = log_mel_a.ravel()
    flat_b = log_mel_b.ravel()
    std_a = float(np.std(flat_a))
    std_b = float(np.std(flat_b))
    if std_a == 0.0 or std_b == 0.0:
        return 0.0
    mean_a = float(np.mean(flat_a))
    mean_b = float(np.mean(flat_b))
    return float(np.mean((flat_a - mean_a) * (flat_b - mean_b)) / (std_a * std_b))


# ---------------------------------------------------------------------------
# Chunked metrics over a DTW-warped pair
# ---------------------------------------------------------------------------


def _warp_slices(
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
    path: list[tuple[int, int]],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Materialise the DTW-warped sequences as same-length arrays.

    Each step of ``path`` indexes one row from each spectrogram; the
    result is two arrays of shape ``(len(path), n_mels)`` aligned
    point-for-point in warped time.
    """
    idx_a = np.fromiter((p[0] for p in path), dtype=np.int64, count=len(path))
    idx_b = np.fromiter((p[1] for p in path), dtype=np.int64, count=len(path))
    return log_mel_a[idx_a], log_mel_b[idx_b]


def chunk_metrics(
    log_mel_a: NDArray[np.float64],
    log_mel_b: NDArray[np.float64],
    path: list[tuple[int, int]],
    *,
    hop_ms: float,
    chunk_ms: float = 500.0,
    n_coefs: int = DEFAULT_MFCC_COEFS,
) -> list[ChunkMetric]:
    """Per-chunk MCD / LSD / correlation along a DTW warp path.

    Args:
        log_mel_a: First (pre-warp) log-mel spectrogram.
        log_mel_b: Second (pre-warp) log-mel spectrogram.
        path: DTW warp path from :func:`dtw_align`.
        hop_ms: Frame hop length in milliseconds (used to translate
            chunk boundaries from frames to wall-clock time).
        chunk_ms: Chunk size in warped-time milliseconds. Default 500 ms
            is roughly two-syllable scale.
        n_coefs: MFCC coefficient count for MCD.

    Returns:
        One :class:`ChunkMetric` per chunk, in warped-time order.
    """
    aligned_a, aligned_b = _warp_slices(log_mel_a, log_mel_b, path)
    n_path = aligned_a.shape[0]
    chunk_frames = max(round(chunk_ms / hop_ms), 1)
    out: list[ChunkMetric] = []
    for c, start in enumerate(range(0, n_path, chunk_frames)):
        stop = min(start + chunk_frames, n_path)
        slice_a = aligned_a[start:stop]
        slice_b = aligned_b[start:stop]
        out.append(
            ChunkMetric(
                index=c,
                start_ms=start * hop_ms,
                end_ms=stop * hop_ms,
                n_frames=stop - start,
                mcd_db=mcd_db(slice_a, slice_b, n_coefs=n_coefs),
                lsd_db=lsd_db(slice_a, slice_b),
                correlation=correlation(slice_a, slice_b),
            )
        )
    return out


def trim_silence(
    samples: NDArray[np.int16],
    *,
    rms_threshold: float = 200.0,
    window: int = 200,
) -> NDArray[np.int16]:
    """Drop leading and trailing silence from an int16 audio array.

    The two pipelines (Python port vs FONIX binary) emit different
    amounts of leading and trailing silence — the binary in particular
    pads the tail by 100s of milliseconds. Comparing un-trimmed audio
    means DTW spends the silence end aligning binary's tail-silence
    against Python's non-silence content, dominating the MCD with
    cepstral noise from log-floor regions.

    Args:
        samples: ``int16`` PCM signal.
        rms_threshold: Per-window RMS (in int16 LSBs) above which a
            window counts as "non-silent". 200 ≈ -45 dBFS, well below
            voiced amplitudes but above quantisation noise.
        window: Size of the RMS-detection window in samples.

    Returns:
        A view into ``samples`` covering only the speech region. If no
        window crosses the threshold, ``samples`` is returned unchanged.
    """
    if samples.size < window:
        return samples
    n_full = samples.size // window
    rms = np.sqrt(
        (samples[: n_full * window].astype(np.float64).reshape(n_full, window) ** 2).mean(axis=1)
    )
    speech = rms > rms_threshold
    if not bool(speech.any()):
        return samples
    first_idx = int(np.argmax(speech)) * window
    # argmax on the reversed array gives the offset of the last True
    # window from the right.
    last_idx = (n_full - int(np.argmax(speech[::-1]))) * window
    return samples[first_idx:last_idx]


def compare(
    samples_a: NDArray[np.int16],
    samples_b: NDArray[np.int16],
    *,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
    n_mels: int = DEFAULT_N_MELS,
    fmin_hz: float = DEFAULT_FMIN_HZ,
    fmax_hz: float = DEFAULT_FMAX_HZ,
    chunk_ms: float = 500.0,
    band: float = DEFAULT_DTW_BAND,
    n_coefs: int = DEFAULT_MFCC_COEFS,
    trim: bool = True,
) -> ComparisonResult:
    """One-shot Python-vs-binary spectrogram comparison.

    Convenience entry point that wires together
    :func:`log_mel_spectrogram`, :func:`dtw_align`, and
    :func:`chunk_metrics`. Used by ``scripts/diagnose_audio.py``.

    Args:
        samples_a: First ``int16`` PCM signal.
        samples_b: Second ``int16`` PCM signal.
        sample_rate_hz: Sample rate (Hz) for both signals.
        n_fft: STFT window length.
        hop: STFT hop length.
        n_mels: Mel filterbank size.
        fmin_hz: Lowest mel-filter center frequency.
        fmax_hz: Highest mel-filter center frequency.
        chunk_ms: Chunk size in warped-time milliseconds.
        band: DTW Sakoe-Chiba band fraction.
        n_coefs: MFCC coefficient count for MCD.
        trim: When ``True`` (default), strip leading and trailing
            silence from both signals before the comparison so that
            DTW doesn't waste warp budget aligning binary's tail
            silence against Python's content.

    Returns:
        :class:`ComparisonResult` with per-chunk and aggregate metrics.
    """
    if trim:
        samples_a = trim_silence(samples_a)
        samples_b = trim_silence(samples_b)
    log_mel_a = log_mel_spectrogram(
        samples_a,
        sample_rate_hz=sample_rate_hz,
        n_fft=n_fft,
        hop=hop,
        n_mels=n_mels,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    log_mel_b = log_mel_spectrogram(
        samples_b,
        sample_rate_hz=sample_rate_hz,
        n_fft=n_fft,
        hop=hop,
        n_mels=n_mels,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    path, _ = dtw_align(log_mel_a, log_mel_b, band=band)
    aligned_a, aligned_b = _warp_slices(log_mel_a, log_mel_b, path)
    hop_ms = 1000.0 * hop / sample_rate_hz
    chunks = chunk_metrics(
        log_mel_a,
        log_mel_b,
        path,
        hop_ms=hop_ms,
        chunk_ms=chunk_ms,
        n_coefs=n_coefs,
    )
    return ComparisonResult(
        n_frames_a=log_mel_a.shape[0],
        n_frames_b=log_mel_b.shape[0],
        path_length=len(path),
        warp_ratio=len(path) / max(log_mel_a.shape[0], log_mel_b.shape[0]),
        global_mcd_db=mcd_db(aligned_a, aligned_b, n_coefs=n_coefs),
        global_lsd_db=lsd_db(aligned_a, aligned_b),
        chunks=chunks,
    )
