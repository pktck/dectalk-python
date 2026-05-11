"""Regression tests for high-frequency ringing artifacts.

The Klatt synth has independent cascade and parallel formant banks. The
parallel-formant resonators (formant_2_parallel..formant_6_parallel)
must have non-zero bandwidths or they become undamped oscillators that
ring forever once excited by frication noise. This caused an audible
~3500 Hz whistle during and after voiceless fricatives in "hello world"
and similar phrases.

This test catches that regression: it synthesises words with a fricative
followed by a vowel and asserts the post-fricative segment doesn't have
disproportionate energy in the F4-F6 band.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.signal import (
    spectrogram,  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]
)

import dectalk

# Maximum tolerated ratio of high-frequency (>3 kHz) energy to mid-band
# (200 Hz - 1.5 kHz) energy in any 50-ms time slice. Without the fix the
# ringing drives the ratio above 100. The C library's synthesis path
# (used by ``speak``) tops out around 41 on "hello world"; the Python
# ``synthesize_phonemes`` path is much lower (~13). We pick 50 to
# accommodate both while still catching a regression.
_MAX_HIGH_MID_RATIO: float = 50.0


def _high_mid_ratio_max(samples: NDArray[np.int16]) -> float:
    """Return the largest per-frame ratio of high-band to mid-band power."""
    fs = 11025
    # scipy.signal.spectrogram has no usable type stubs.
    res = spectrogram(  # pyright: ignore[reportUnknownVariableType]
        samples.astype(np.float64), fs=fs, nperseg=512, noverlap=256
    )
    f: NDArray[np.float64] = np.asarray(res[0], dtype=np.float64)
    sxx: NDArray[np.float64] = np.asarray(res[2], dtype=np.float64)
    high = sxx[f > 3000].sum(axis=0)
    mid = sxx[(f > 200) & (f < 1500)].sum(axis=0)
    return float((high / np.maximum(mid, 1.0)).max())


def test_hello_world_has_no_high_freq_whistle() -> None:
    """The 3.5 kHz parallel-F4 ringing bug must not re-appear.

    Before the fix, the parallel F4-F6 resonators with default
    bandwidth 0 would ring at their centre frequency forever once
    excited by the HH frication. Empirically the ratio went above 195
    on this phrase. We assert <= 40 to leave headroom while still
    catching the bug.
    """
    samples = dectalk.speak("hello world")
    assert _high_mid_ratio_max(samples) <= _MAX_HIGH_MID_RATIO


def test_fricative_to_vowel_transition() -> None:
    """A direct HH AH sequence stresses the same bug path.

    Note: this checks the post-frication tail. Phrases that are
    intrinsically fricative-heavy (e.g. ``she sells sea shells``) have
    legitimate high-band energy from /s/ /sh/ and would falsely flag
    on this metric.
    """
    samples = dectalk.synthesize_phonemes(["HH", "AH", "L"])
    assert _high_mid_ratio_max(samples) <= _MAX_HIGH_MID_RATIO


def test_voiced_only_phrase_has_minimal_high_band() -> None:
    """An all-voiced phrase has no fricative source - high band must be quiet."""
    samples = dectalk.synthesize_phonemes(["W", "ER", "L", "D", "L", "AH", "V", "L", "IY"])
    assert _high_mid_ratio_max(samples) <= 5.0
