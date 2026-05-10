"""Unit tests for the spectrogram comparison utilities.

The harness backs the per-prompt acoustic-similarity gating in
``scripts/diagnose_audio.py``; the tests below pin its core
invariants without exercising the synthesiser or binary, so they run
in well under a second.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from dectalk import _audio_compare as sc


def _sine(freq_hz: float, duration_s: float, sample_rate_hz: int = 11025) -> NDArray[np.int16]:
    """Return a fixed-amplitude int16 sine wave."""
    n = int(duration_s * sample_rate_hz)
    t = np.arange(n) / sample_rate_hz
    wave = 0.4 * np.sin(2.0 * np.pi * freq_hz * t)
    return (wave * 32767.0).astype(np.int16)


class TestMelFilterbank:
    """Cover the mel filterbank helper."""

    def test_filterbank_shape_matches_n_fft(self) -> None:
        fb = sc.mel_filterbank(n_fft=512, n_mels=64)
        assert fb.shape == (64, 257)

    def test_each_filter_has_a_peak(self) -> None:
        fb = sc.mel_filterbank(n_fft=512, n_mels=64)
        # Each row should reach 1.0 at its centre (per the triangular
        # construction).
        peaks = fb.max(axis=1)
        assert np.all(peaks > 0.0)

    def test_filters_overlap_neighbours(self) -> None:
        fb = sc.mel_filterbank(n_fft=512, n_mels=16)
        # Adjacent filters share at least one nonzero bin (otherwise the
        # mel projection has gaps that bias the spectrogram).
        for m in range(fb.shape[0] - 1):
            both_nonzero = (fb[m] > 0.0) & (fb[m + 1] > 0.0)
            assert np.any(both_nonzero), f"filters {m} and {m + 1} have no overlap"


class TestLogMelSpectrogram:
    """Cover the STFT + log-mel front end."""

    def test_int16_and_float_inputs_match(self) -> None:
        sig_i16 = _sine(440.0, 0.2)
        sig_f64 = sig_i16.astype(np.float64) / 32768.0
        from_i16 = sc.log_mel_spectrogram(sig_i16)
        from_f64 = sc.log_mel_spectrogram(sig_f64)
        np.testing.assert_allclose(from_i16, from_f64, rtol=1e-9, atol=1e-9)

    def test_silence_is_floor(self) -> None:
        silence = np.zeros(2048, dtype=np.int16)
        log_mel = sc.log_mel_spectrogram(silence)
        # 20 * log10(_LOG_FLOOR) = -200 dB.
        assert log_mel.max() < -100.0

    def test_short_input_padded_to_at_least_one_frame(self) -> None:
        # 100 samples is below the 512-sample FFT window; the helper must
        # still produce one frame rather than a 0-length output.
        tiny = _sine(440.0, 0.01)[:100]
        log_mel = sc.log_mel_spectrogram(tiny)
        assert log_mel.shape[0] >= 1
        assert log_mel.shape[1] == sc.DEFAULT_N_MELS


class TestDtwAlign:
    """Cover the band-constrained DTW aligner."""

    def test_identical_signals_align_diagonally(self) -> None:
        sig = _sine(220.0, 0.5)
        log_mel = sc.log_mel_spectrogram(sig)
        path, mean_cost = sc.dtw_align(log_mel, log_mel)
        # Path traces the diagonal exactly when both signals are equal.
        assert path[0] == (0, 0)
        assert path[-1] == (log_mel.shape[0] - 1, log_mel.shape[0] - 1)
        for i, j in path:
            assert i == j
        # Cost must be effectively zero for equal inputs (small float
        # error from the squared-norm broadcast trick is tolerated).
        assert abs(mean_cost) < 1e-4

    def test_alignment_cost_grows_with_pitch_disagreement(self) -> None:
        log_mel_a = sc.log_mel_spectrogram(_sine(220.0, 0.5))
        log_mel_b = sc.log_mel_spectrogram(_sine(330.0, 0.5))
        log_mel_c = sc.log_mel_spectrogram(_sine(880.0, 0.5))
        _, cost_close = sc.dtw_align(log_mel_a, log_mel_b)
        _, cost_far = sc.dtw_align(log_mel_a, log_mel_c)
        assert cost_far > cost_close

    def test_path_endpoints_pinned(self) -> None:
        log_mel_a = sc.log_mel_spectrogram(_sine(220.0, 0.5))
        log_mel_b = sc.log_mel_spectrogram(_sine(220.0, 0.7))
        path, _ = sc.dtw_align(log_mel_a, log_mel_b)
        assert path[0] == (0, 0)
        assert path[-1] == (log_mel_a.shape[0] - 1, log_mel_b.shape[0] - 1)

    def test_band_widens_when_too_tight(self) -> None:
        # A 30 % duration mismatch with a 5 % band would normally fail to
        # reach the corner; the implementation widens and retries.
        log_mel_a = sc.log_mel_spectrogram(_sine(220.0, 0.5))
        log_mel_b = sc.log_mel_spectrogram(_sine(220.0, 0.65))
        path, _ = sc.dtw_align(log_mel_a, log_mel_b, band=0.05)
        assert path[-1] == (log_mel_a.shape[0] - 1, log_mel_b.shape[0] - 1)

    def test_empty_input_raises(self) -> None:
        empty = np.zeros((0, sc.DEFAULT_N_MELS), dtype=np.float64)
        nonempty = sc.log_mel_spectrogram(_sine(220.0, 0.1))
        with pytest.raises(ValueError, match="empty input"):
            sc.dtw_align(empty, nonempty)
        with pytest.raises(ValueError, match="empty input"):
            sc.dtw_align(nonempty, empty)

    def test_negative_band_raises(self) -> None:
        log_mel = sc.log_mel_spectrogram(_sine(220.0, 0.1))
        with pytest.raises(ValueError, match="band must be non-negative"):
            sc.dtw_align(log_mel, log_mel, band=-0.1)


class TestDistanceMetrics:
    """Cover MCD / LSD / correlation."""

    def test_identical_inputs_give_zero_distance(self) -> None:
        sig = _sine(440.0, 0.4)
        log_mel = sc.log_mel_spectrogram(sig)
        assert abs(sc.mcd_db(log_mel, log_mel)) < 1e-9
        assert abs(sc.lsd_db(log_mel, log_mel)) < 1e-9
        assert abs(sc.correlation(log_mel, log_mel) - 1.0) < 1e-6

    def test_mcd_and_lsd_grow_with_signal_difference(self) -> None:
        log_mel_a = sc.log_mel_spectrogram(_sine(220.0, 0.4))
        log_mel_b = sc.log_mel_spectrogram(_sine(330.0, 0.4))
        log_mel_c = sc.log_mel_spectrogram(_sine(880.0, 0.4))
        # Truncate to common length (durations are equal so they match,
        # but we guard against any rounding-induced 1-frame slack).
        n = min(log_mel_a.shape[0], log_mel_b.shape[0], log_mel_c.shape[0])
        a, b, c = log_mel_a[:n], log_mel_b[:n], log_mel_c[:n]
        assert sc.mcd_db(a, c) > sc.mcd_db(a, b)
        assert sc.lsd_db(a, c) > sc.lsd_db(a, b)

    def test_shape_mismatch_raises(self) -> None:
        log_mel_a = sc.log_mel_spectrogram(_sine(220.0, 0.4))
        log_mel_b = sc.log_mel_spectrogram(_sine(220.0, 0.6))
        # Different frame counts must raise a clear error from the
        # metric helpers (they expect already-aligned inputs).
        with pytest.raises(ValueError, match="shape mismatch"):
            sc.mcd_db(log_mel_a, log_mel_b)
        with pytest.raises(ValueError, match="shape mismatch"):
            sc.lsd_db(log_mel_a, log_mel_b)

    def test_correlation_handles_constant_input(self) -> None:
        # All-floor log-mel produces zero variance; correlation should
        # bail out with 0.0 rather than NaN.
        constant = np.full((20, sc.DEFAULT_N_MELS), -200.0, dtype=np.float64)
        non_constant = sc.log_mel_spectrogram(_sine(440.0, 0.3))
        n = min(constant.shape[0], non_constant.shape[0])
        assert sc.correlation(constant[:n], non_constant[:n]) == 0.0


class TestChunkMetrics:
    """Cover per-chunk slicing along a DTW warp path."""

    def test_chunk_count_matches_path_length(self) -> None:
        sig_a = _sine(220.0, 0.6)
        sig_b = _sine(220.0, 0.6)
        log_mel_a = sc.log_mel_spectrogram(sig_a)
        log_mel_b = sc.log_mel_spectrogram(sig_b)
        path, _ = sc.dtw_align(log_mel_a, log_mel_b)
        hop_ms = 1000.0 * sc.DEFAULT_HOP / sc.DEFAULT_SAMPLE_RATE_HZ
        chunks = sc.chunk_metrics(log_mel_a, log_mel_b, path, hop_ms=hop_ms, chunk_ms=200.0)
        # 600 ms split into 200 ms chunks => 3 (allowing one ragged tail).
        assert 2 <= len(chunks) <= 4

    def test_identical_inputs_give_zero_per_chunk_mcd(self) -> None:
        log_mel = sc.log_mel_spectrogram(_sine(220.0, 0.5))
        path, _ = sc.dtw_align(log_mel, log_mel)
        hop_ms = 1000.0 * sc.DEFAULT_HOP / sc.DEFAULT_SAMPLE_RATE_HZ
        chunks = sc.chunk_metrics(log_mel, log_mel, path, hop_ms=hop_ms, chunk_ms=200.0)
        for chunk in chunks:
            assert abs(chunk.mcd_db) < 1e-9
            assert abs(chunk.lsd_db) < 1e-9
            assert abs(chunk.correlation - 1.0) < 1e-6


class TestCompareEntryPoint:
    """Cover the one-shot ``compare`` convenience wrapper."""

    def test_identical_audio_passes_clean(self) -> None:
        sig = _sine(440.0, 0.5)
        result = sc.compare(sig, sig)
        assert abs(result.warp_ratio - 1.0) < 1e-6
        assert abs(result.global_mcd_db) < 1e-9
        assert abs(result.global_lsd_db) < 1e-9
        assert abs(result.chunk_mcd_mean) < 1e-9
        assert abs(result.chunk_mcd_p95) < 1e-9

    def test_path_at_least_longer_axis_when_durations_differ(self) -> None:
        sig_a = _sine(440.0, 0.5)
        sig_b = _sine(440.0, 0.7)
        result = sc.compare(sig_a, sig_b)
        # Optimal DTW warps the shorter side to align with the longer
        # side: path length equals max(n_a, n_b) when no extra
        # repetition is needed beyond filling the longer axis.
        assert result.path_length >= max(result.n_frames_a, result.n_frames_b)
        # warp_ratio normalises to [1.0, 2.0]: 1.0 means optimal
        # frame-for-frame alignment along the longer axis.
        assert result.warp_ratio >= 1.0

    def test_chunks_cover_full_warped_path(self) -> None:
        sig = _sine(440.0, 0.5)
        result = sc.compare(sig, sig, chunk_ms=200.0)
        total_frames = sum(c.n_frames for c in result.chunks)
        assert total_frames == result.path_length
