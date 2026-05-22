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
        # Upper bounds widened in issue #72: the trailing-silence pad
        # adds ~6-9k samples per clause so the pure-Python pipeline now
        # closer matches the C reference's trailing-pad behaviour.
        ("hi", 2000, 12000),
        ("hello world", 7000, 24000),
        ("good morning", 7000, 24000),
        ("test one two three", 11000, 30000),
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


def test_full_pipeline_inline_command_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """``[:rate N]`` no longer emits spelled-out command audio (issue #64).

    Before the parse-routing fix, ``[:rate 250] testing one two three``
    produced ~34540 samples because the full pipeline tokenised the
    literal ``[:``, ``rate``, ``250``, ``]`` as words and LTS-spelled
    them ("rate two hundred and fifty …"). After the fix, the directive
    mutates per-segment state and the rendered audio is only the
    content phrase (much shorter — the rate=2.5x WPM also compresses
    duration in the full pipeline's current wiring).
    """
    samples = _speak("[:rate 250] testing one two three", monkeypatch)
    # Bare "testing one two three" at rate=1.0 produces ~11-22k samples
    # (see parametrize bounds above for similar prompts). With the
    # spelled-out "rate two hundred and fifty" stripped out, the rendered
    # audio is strictly under that — and far less than the pre-fix 34540.
    assert samples.size < 20_000, (
        f"inline [:rate 250] not stripped — got {samples.size} samples "
        "(suggests command words leaked into LTS as in issue #64)"
    )
    # Non-empty: the content phrase still synthesises.
    assert samples.size > 1500, f"content phrase missing — got {samples.size} samples"


def test_full_pipeline_inline_voice_change_synthesises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``[:dv NAME]`` selects a voice without spelling out ``dv``/``NAME``."""
    samples = _speak("[:dv betty] hello", monkeypatch)
    # Should be similar in size to plain "hello" — the ``[:dv betty]``
    # directive mutates state without emitting phones.
    plain = _speak("hello", monkeypatch)
    # Within 50% of plain "hello" size (allow some slack for voice
    # parameter differences once those are threaded through).
    assert 0.5 * plain.size <= samples.size <= 1.5 * plain.size, (
        f"[:dv betty] hello={samples.size}, plain hello={plain.size} -- "
        "the command may have leaked into the phone stream"
    )


# ---------------------------------------------------------------------------
# Trailing-silence pad (issue #72) -- the per-frame loop in
# `_speak_via_python_full` used to terminate on `nphone >= nallotot`
# without honouring the C reference's clause-final long-pause GEN_SIL
# duration. Audio ended mid-frame with zero trailing silence; the C
# binary appends ~3900-4400 samples (~360 ms) of zeros at clause end.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "hello world",
        "the quick brown fox",
        "one two three four five",
        "test",
        "a",
    ],
)
def test_full_pipeline_emits_trailing_silence(
    text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full-pipeline output ends with a run of zero samples (issue #72).

    Mirrors the C reference's behaviour: ``us_phtiming``'s Rule 1
    (``p_us_tim.c`` line 309) substitutes ``nfperiod + perpause +
    asperation`` for the default short pause when the previous
    allophone's ``FBOUNDARY`` field carries ``FSENTENDS``. Without the
    fix the trailing GEN_SIL ran for ~14 frames and the synth's AV
    ramp-down never reached true zero before the clause ended; with
    the fix the trailing-SIL ``allodurs`` value rises to ~70 frames,
    enough headroom for the synth to emit a long zero-amplitude tail.

    The exact length depends on synth-state divergence with the C
    reference (out of scope for this issue) so the assertion is just
    "more than 500 trailing zeros" — well above the pre-fix value
    of zero, well below pathological runaway.
    """
    samples = _speak(text, monkeypatch)
    assert samples.size > 0, f"{text!r} produced no audio"
    nonzero = np.flatnonzero(samples != 0)
    assert nonzero.size > 0, f"{text!r} produced all-zero audio"
    trail = int(samples.size - nonzero[-1] - 1)
    assert trail > 500, (
        f"{text!r}: trailing-silence pad is {trail} samples (was 0 pre-#72); "
        "the per-frame loop is dropping the trailing GEN_SIL allophone."
    )
    # Sanity upper bound: at 11025 Hz, 22050 samples == 2 s of silence.
    # The C reference's pad is ~360 ms; the Python pad is currently
    # ~600-900 ms (synth AV-ramp behaviour differs). Anything past 2 s
    # would indicate a buggy looping condition.
    assert trail < 22_050, (
        f"{text!r}: trailing-silence pad is {trail} samples (>2 s) -- "
        "the per-frame loop is not terminating correctly."
    )
