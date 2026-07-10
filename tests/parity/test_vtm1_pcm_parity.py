"""Parity test: ``DECTALK_USE_VTM1=1`` PCM output vs the C oracle WAV.

Acceptance test for issue #158 — verifies the alternative vtm1 synth
path produces audio that matches the C oracle's WAV output for a small
set of representative prompts.

**Current status (Phase E rollout, issue #297)**: 348/500 of the
stratified corpus sample renders **byte-identical** from pure Python
on the FULL+VTM1 path. This file holds three tiers of gate:

1. Smoke: the vtm1 path produces *some* int16 PCM for the prompts.
2. Sample-count exactness on the #270 audit set (wide-tolerance
   length checks retained for the legacy smoke prompts).
3. **Byte-identical WAV equality** on ``_BYTE_EXACT_PROMPTS`` — a
   hard pass since #297, one pinned prompt group per fixed
   divergence cluster.

Skips cleanly when the C oracle artefacts are missing.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from dectalk.api.speak import _speak_via_python_full

_DECTALK_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_DECTALK_BIN = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True when both the source-built libtts and the shipped binary exist."""
    has_src = any(_DECTALK_SRC.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    has_bin = (_DECTALK_BIN / "say").is_file() and (_DECTALK_BIN / "DECtalk.conf").is_file()
    return has_src and has_bin


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not _have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


# Small corpus the PH stage handles well today. Longer / inflected
# prompts diverge more (the PH timing port is incomplete).
_PROMPTS: tuple[str, ...] = ("hi", "hello", "test")


def _binary_pcm_int16(text: str) -> np.ndarray:
    """Render ``text`` via the shipped binary and return int16 PCM samples."""
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "ref.wav"
        subprocess.run(
            [str(_DECTALK_BIN / "say"), "-a", text, "-fo", str(wav_path)],
            cwd=str(_DECTALK_BIN),
            check=True,
            capture_output=True,
        )
        with wave.open(str(wav_path), "rb") as fh:
            raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _python_vtm1_pcm(text: str, monkeypatch: pytest.MonkeyPatch) -> np.ndarray:
    """Render ``text`` via the Python ``DECTALK_USE_VTM1`` path."""
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    monkeypatch.setenv("DECTALK_USE_VTM1", "1")
    return _speak_via_python_full(text, 1.0, None, "us", True)


@pytest.mark.parametrize("text", _PROMPTS)
def test_vtm1_produces_nontrivial_pcm(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The vtm1 synth path produces non-empty int16 audio for the prompt."""
    samples = _python_vtm1_pcm(text, monkeypatch)
    assert samples.dtype == np.int16
    assert samples.size > 0, f"vtm1 path produced zero samples for {text!r}"
    assert np.any(samples != 0), f"vtm1 path produced all-zero samples for {text!r}"


@pytest.mark.parametrize("text", _PROMPTS)
def test_vtm1_pcm_length_within_tolerance(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 PCM length is within a wide tolerance of the C oracle.

    Until the PH timing layer ports (Phase E), exact length parity is
    not expected. This test enforces a 50% length tolerance to catch
    egregious regressions (e.g. the path producing zero or 100x output).
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size > 0
    assert ref.size > 0
    ratio = py.size / ref.size
    assert 0.5 <= ratio <= 2.0, (
        f"vtm1 PCM length {py.size} vs C oracle {ref.size} (ratio {ratio:.2f}) "
        f"outside the 50% tolerance — likely a wiring regression"
    )


# Prompts whose FULL+VTM1 sample count is exactly the C oracle's after
# the #270 timing fixes (sole-secondary lexicon stress alignment,
# per-clause phclause segmentation, HLSYN-only WBOUND step-past
# removal). Byte-level content still diverges (Phase E frame-content
# work), but the per-allophone durations — and therefore the total
# sample count — are phone-for-phone equal to the oracle. Pinned as a
# hard gate so timing regressions surface immediately.
_COUNT_EXACT_PROMPTS: tuple[str, ...] = (
    "hello world",
    "testing one two three",
    "the quick brown fox",
    "a box of cats",
    "and then we left",
    "chairs, tables, lamps, and rugs",
)


@pytest.mark.parametrize("text", _COUNT_EXACT_PROMPTS)
def test_vtm1_pcm_sample_count_exact(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python FULL+VTM1 sample count equals the C oracle's exactly.

    Issue #270: the per-allophone durations on these prompts match the
    oracle phone-for-phone (verified via the OUT_PH/OUT_DU cells of
    ``vtm_frames.dump``), so the emitted frame count — and the PCM
    sample count — must be identical. This is the timing-layer parity
    gate; byte equality remains tracked by the xfail test below.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, (
        f"sample-count drift for {text!r}: Python {py.size} vs C {ref.size} "
        f"({(py.size - ref.size) / _SAMPLES_PER_FRAME:+.1f} frames)"
    )


# Prompts pinned BYTE-IDENTICAL to the oracle WAV on the FULL+VTM1
# path — the Phase E goal metric, held as a **hard** gate (issue #297;
# 348/500 of the corpus sample render byte-exact as of the #297 fixes).
# Each group pins a named divergence-cluster fix so a regression names
# its cluster directly:
#   - "hi" / "hello" / "test": the original #158 smoke prompts (were
#     xfail; flipped by the #283..#294 wave and promoted here).
#   - "hello world" / "the quick brown fox" / "chairs, tables, lamps,
#     and rugs": the #270 count-exact gate prompts, now byte-exact.
#   - "BBC" / "bite" / "stop!": the pht0draw OUT_PH/OUT_DU per-frame
#     overwrite (ph_drwt01.c:3021-3024) feeding the vtm1.c:1318
#     silence ramp-down gate — the #297 primary cluster (+115 prompts).
#   - "MRI" / "wait, he is honest": the live consonant→stressed-vowel
#     glottal branch in the active set_tglst (ph_drwt01.c:3118).
#   - "listen down" / "my dog is near the bedroom": primary-only
#     stress counting in remaining_stresses_til (ph_aloph1.c:1566)
#     placing the FHAT_ENDS hat fall on the last *primary* stress.
_BYTE_EXACT_PROMPTS: tuple[str, ...] = (
    "hi",
    "hello",
    "test",
    "hello world",
    "the quick brown fox",
    "chairs, tables, lamps, and rugs",
    "BBC",
    "bite",
    "stop!",
    "MRI",
    "wait, he is honest",
    "listen down",
    "my dog is near the bedroom",
)


@pytest.mark.parametrize("text", _BYTE_EXACT_PROMPTS)
def test_vtm1_pcm_byte_identical_to_oracle(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 PCM is byte-identical to the C oracle's WAV.

    Hard pass (no xfail) since issue #297: the pure-Python FULL+VTM1
    render is byte-identical on every prompt above. The vtm1
    synth-stage port itself is verified by
    ``test_vtm_speech_waveform_generator_parity`` and the synth-state
    seeding by ``test_vtm_pump_frames``; this asserts the whole
    PH-parameter + synth chain end to end.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, f"length mismatch {py.size} vs {ref.size}"
    np.testing.assert_array_equal(py, ref)


# Frame size at the active 11025 Hz build (vtm1.c uiNumberOfSamplesPerFrame).
_SAMPLES_PER_FRAME = 71

# Prompts whose leading silence is governed entirely by the speaker-def
# silence latch: a leading GEN_SIL phone followed directly by a voiced
# onset, so the oracle's first audible sample is the latch boundary at
# frame 3 (sample 213) with no extra leading silent phones. Prompts that
# open on a stop closure (e.g. "test") or a different onset accrue extra
# leading silence from phone timing — a separate barrier — so they are
# intentionally excluded here (issue #266).
_LEADING_SILENCE_PROMPTS: tuple[str, ...] = (
    "hello world",
    "hello",
    "hi",
    "how are you",
)


def _first_audio_sample(pcm: np.ndarray) -> int:
    """Index of the first non-zero sample, or ``-1`` if all-zero."""
    nz = np.nonzero(pcm)[0]
    return int(nz[0]) if nz.size else -1


@pytest.mark.parametrize("text", _LEADING_SILENCE_PROMPTS)
def test_vtm1_leading_silence_matches_oracle(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 leading silence matches the C oracle's, frame-for-frame.

    The shipped ``libtts_us.so`` holds three leading frames as real
    silence after the speaker-definition packet (``vtm1.c`` ``ldspdef``
    latch). On ``hello world`` the oracle's first non-zero sample is 213
    (frame 3); the Python vtm1 path previously emitted aspiration one
    frame early (first non-zero at 142, frame 2), which was the first
    byte divergence. This pins the fix as a *parity* assertion — the
    Python first-audio sample equals the oracle's, and every leading
    silent frame is byte-identical (all-zero in both) — rather than
    hard-coding the magic frame index (issue #266).
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)

    ref_first = _first_audio_sample(ref)
    py_first = _first_audio_sample(py)

    assert ref_first >= 0, f"oracle produced all-zero PCM for {text!r}"
    # The Python first-audio sample must match the oracle's exactly: the
    # leading silence is byte-identical up to (and not past) that point.
    assert py_first == ref_first, (
        f"vtm1 leading silence diverges for {text!r}: Python first-audio "
        f"sample {py_first} (frame {py_first / _SAMPLES_PER_FRAME:.2f}) vs "
        f"oracle {ref_first} (frame {ref_first / _SAMPLES_PER_FRAME:.2f})"
    )

    # Every fully-leading silent frame must be all-zero in both streams
    # (the byte-identical-prefix claim, restricted to the silent region).
    leading_silent_frames = ref_first // _SAMPLES_PER_FRAME
    silent_len = leading_silent_frames * _SAMPLES_PER_FRAME
    np.testing.assert_array_equal(
        py[:silent_len],
        ref[:silent_len],
        err_msg=f"leading silent frames differ for {text!r}",
    )
    if silent_len:
        assert not np.any(py[:silent_len]), f"Python leading frames not silent for {text!r}"
