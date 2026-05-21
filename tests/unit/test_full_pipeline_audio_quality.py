"""Audio-quality smoke tests for the pure-Python full pipeline.

Tracks gross output properties of ``DECTALK_FULL_PIPELINE=1`` so we can see
regressions in the wiring layer at a glance. Distinct from
``tests/parity/test_binary_wav_parity.py`` which asserts byte-identical
output vs. the C binary; these tests track only "the pure-Python output
is sane" -- non-zero, non-clipping, within reasonable length bounds.

The tests are unit-level (not c_oracle-marked) so they run on every
``pytest`` invocation and surface regressions in the wiring layer fast.
"""

from __future__ import annotations

import numpy as np
import pytest


def _speak(text: str, monkeypatch: pytest.MonkeyPatch) -> np.ndarray:
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    from dectalk.api.speak import _speak_via_python  # noqa: PLC0415

    return _speak_via_python(
        text=text,
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )


@pytest.mark.parametrize(
    ("text", "min_samples", "max_samples"),
    [
        ("hi", 2000, 7000),
        ("hello world", 7000, 16000),
        ("good morning", 7000, 16000),
        ("test one two three", 11000, 22000),
    ],
)
def test_full_pipeline_sample_count_in_range(
    text: str,
    min_samples: int,
    max_samples: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sample counts stay in the same order of magnitude as the C oracle."""
    samples = _speak(text, monkeypatch)
    assert min_samples <= samples.size <= max_samples, (
        f"{text!r}: {samples.size} samples outside [{min_samples}, {max_samples}]"
    )


def test_full_pipeline_no_clipping(monkeypatch: pytest.MonkeyPatch) -> None:
    """No samples saturate at int16 max (clipping is a parity regression)."""
    samples = _speak("hello world", monkeypatch)
    abs_s = np.abs(samples.astype(np.int32))
    clip_frac = (abs_s >= 32700).sum() / max(1, samples.size)
    assert clip_frac < 0.01, f"clipping at {clip_frac:.1%}"


def test_full_pipeline_signal_has_audible_amplitude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mean abs amplitude is audible (not all near-zero)."""
    samples = _speak("hello world", monkeypatch)
    mean_abs = int(np.abs(samples).mean())
    assert mean_abs > 500, f"mean abs {mean_abs} -- voicing collapsed?"


def test_full_pipeline_signal_has_variation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Samples vary across the clause (not a stuck DC offset)."""
    samples = _speak("hello world", monkeypatch)
    std = int(samples.std())
    assert std > 1000, f"std {std} -- signal stuck near DC?"
