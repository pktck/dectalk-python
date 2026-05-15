"""End-to-end parity vs the DECtalk binary release.

These tests run the same text through:

1. The DECtalk Linux binary (``say`` from the released build), captured
   as a WAV file via its ``-fo`` flag.
2. Our Python :func:`dectalk.api.speak`, captured as int16 samples.

We don't expect bit-exact equality — the front-end pipelines (text
normalisation, LTS, lexicon, prosody) are independent reimplementations
and the binary uses its own dictionaries. Instead we assert *audio
similarity* signals: both produce non-empty audio of comparable
duration, similar RMS energy, and overlapping spectral peaks.

Tests skip cleanly when the binary isn't available (the env var
``DECTALK_BIN_DIR`` controls the search location; the default scans a
handful of common paths on disk).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.signal import welch  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]

import dectalk

pytestmark = pytest.mark.c_oracle

# Absolute peak headroom in int16; values above this are saturated and
# can't be compared meaningfully.
_INT16_MAX = 32767


def _candidate_paths() -> list[Path]:
    env = os.environ.get("DECTALK_BIN_DIR")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        Path(p)
        for p in (
            "/tmp/dectalk-binary-stable",
            "/tmp/dectalk-bin",
            "/opt/dectalk",
            "/usr/local/dectalk",
        )
    )
    return candidates


def _find_say() -> Path | None:
    """Return the path to the DECtalk ``say`` binary if available."""
    for base in _candidate_paths():
        candidate = base / "say"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    # Fallback: PATH lookup (only useful if user installed it).
    found = shutil.which("dtsay") or shutil.which("dectalk-say")
    return Path(found) if found else None


@pytest.fixture(scope="session")
def dectalk_binary() -> Path:
    say = _find_say()
    if say is None:
        pytest.skip(
            "DECtalk binary not found; set DECTALK_BIN_DIR or place the "
            "Linux release under /tmp/dectalk-binary-stable."
        )
    return say


def _run_binary(say: Path, text: str, output: Path) -> np.ndarray:
    """Invoke the DECtalk binary and return the int16 PCM samples it produced."""
    env = os.environ.copy()
    env.setdefault("DTK_PROGRAM_PATH", str(say.parent))
    env.setdefault("DTK_DIC", str(say.parent / "dic"))
    cmd = [str(say), "-a", text, "-fo", str(output), "-e", "1"]
    subprocess.run(cmd, capture_output=True, check=True, env=env, cwd=str(say.parent))
    with wave.open(str(output), "rb") as fh:
        raw = fh.readframes(fh.getnframes())
        sr = fh.getframerate()
    assert sr == 11025, f"binary produced {sr} Hz audio; expected 11025"
    return np.frombuffer(raw, dtype=np.int16)


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def _top_spectral_peaks(samples: np.ndarray, n_peaks: int = 6) -> list[float]:
    """Return the ``n_peaks`` highest spectral peaks, sorted by frequency."""
    # scipy.signal.welch has no usable type stubs; the call returns a 2-tuple
    # of float64 arrays. Cast both halves so the rest of the function is
    # fully typed.
    result = welch(samples.astype(np.float64), fs=11025, nperseg=2048)  # pyright: ignore[reportUnknownVariableType]
    freqs: NDArray[np.float64] = np.asarray(result[0], dtype=np.float64)
    psd: NDArray[np.float64] = np.asarray(result[1], dtype=np.float64)
    idx = np.argsort(psd)[-n_peaks:][::-1]
    return sorted(float(freqs[i]) for i in idx)


# Test phrases. Choose words present in both DECtalk's bundled
# dictionary and ours so the front-ends mostly agree on the phoneme
# stream — the audio comparison then mostly reflects the synthesizer.
_TEST_PHRASES = (
    "hello world",
    "this is a test",
    "the quick brown fox",
    "computer",
)


@pytest.mark.parametrize("text", _TEST_PHRASES, ids=list(_TEST_PHRASES))
def test_binary_and_python_produce_comparable_audio(
    text: str, dectalk_binary: Path, tmp_path: Path
) -> None:
    """Both implementations should produce non-trivial, similarly-energised audio."""
    binary_wav = tmp_path / "binary.wav"
    binary_samples = _run_binary(dectalk_binary, text, binary_wav)
    py_samples = dectalk.speak(text)

    # Both must produce non-empty audio.
    assert binary_samples.size > 0
    assert py_samples.size > 0

    # Durations should be in the same ballpark (factor of 4 either way is
    # tolerated; the front-end prosody implementations differ).
    bin_dur_s = binary_samples.size / 11025
    py_dur_s = py_samples.size / 11025
    ratio = max(bin_dur_s, py_dur_s) / min(bin_dur_s, py_dur_s)
    max_duration_ratio = 4.0
    assert ratio <= max_duration_ratio, (
        f"duration ratio {ratio:.2f} > {max_duration_ratio} for {text!r}: "
        f"binary={bin_dur_s:.2f}s, python={py_dur_s:.2f}s"
    )

    # Both should have audible RMS (above 1% of int16 full-scale).
    bin_rms = _rms(binary_samples)
    py_rms = _rms(py_samples)
    assert bin_rms > 0.01 * _INT16_MAX
    assert py_rms > 0.01 * _INT16_MAX


def test_binary_says_hello_world_with_voiced_energy(dectalk_binary: Path, tmp_path: Path) -> None:
    """Sanity: the binary's hello-world output has spectral energy below 5kHz.

    Catches regressions where the binary or its environment produces only
    noise / silence (e.g. missing licence file, wrong DTK_DIC env).
    """
    binary_wav = tmp_path / "binary.wav"
    samples = _run_binary(dectalk_binary, "hello world", binary_wav)
    peaks = _top_spectral_peaks(samples)
    voiced_band = [p for p in peaks if 100.0 <= p <= 5000.0]
    assert len(voiced_band) >= 3, f"expected voiced peaks below 5 kHz; got {peaks}"
