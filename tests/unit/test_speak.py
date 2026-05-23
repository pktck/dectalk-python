"""End-to-end tests for the public text → audio API."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from dectalk.api import UnknownWordError, speak, text_to_phonemes, to_wav
from dectalk.api.speak import _pump_frames_to_samples, _speak_via_python
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT


def test_text_to_phonemes_hello_world() -> None:
    phones = text_to_phonemes("hello world")
    assert "HH" in phones
    assert "L" in phones
    assert "ER1" in phones
    assert "D" in phones


def test_text_to_phonemes_inserts_pauses() -> None:
    phones = text_to_phonemes("hello, world.")
    sil_count = phones.count("SIL")
    assert sil_count >= 2  # one for the comma, one for the period


def test_speak_returns_int16_pcm() -> None:
    samples = speak("hello world")
    assert samples.dtype == np.int16
    assert samples.size > 0
    assert int(np.max(np.abs(samples))) > 0


def test_text_to_phonemes_unknown_word_raises_when_lts_disabled() -> None:
    """``text_to_phonemes`` (approximate path) still honours ``lts_fallback``."""
    with pytest.raises(UnknownWordError, match="not in the us lexicon"):
        text_to_phonemes("xyzzynotaword", lts_fallback=False)


def test_speak_pronounces_unknown_word_via_c_lts() -> None:
    """``speak`` routes through _capi; the C library always pronounces."""
    samples = speak("xyzzy")
    assert samples.size > 0


def test_to_wav_writes_valid_file(tmp_path: Path) -> None:
    out = tmp_path / "hello.wav"
    to_wav("hello world", out)
    assert out.exists()
    assert out.stat().st_size > 1000  # synthesis output must be substantial


def test_speak_rate_scales_duration() -> None:
    fast = speak("hello world", rate=0.5)
    slow = speak("hello world", rate=2.0)
    assert fast.size < slow.size


def test_inline_rate_is_absolute_wpm_on_full_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #70 — ``[:rate N]`` is absolute WPM, not a duration multiplier.

    Before this fix, the full Python pipeline interpreted ``[:rate N]``
    as a "rate multiplier" (N=100 == nominal, N=200 == twice as slow)
    and additionally inverted the rate-to-WPM formula compared with
    the C-routed path. The C binary treats ``[:rate N]`` as absolute
    words-per-minute (default 180, range [75, 600]).

    After the fix the Python pipeline's sample counts scale relative
    to N the same way the C oracle's do — bigger N is faster (fewer
    samples), smaller N is slower (more samples), and ``[:rate 180]``
    is indistinguishable from no directive at all.

    This test asserts the relative-scaling invariants in the pure-
    Python full pipeline (gated by ``DECTALK_FULL_PIPELINE=1`` and
    ``DECTALK_DISABLE_CAPI=1``). Absolute bit-parity with the C oracle
    is gated separately by the c_oracle marker — the PH-stage timing
    pipeline has a ~+6% baseline drift documented in
    ``docs/parity-divergence-audit.md`` that is independent of the
    rate-semantics issue this test guards.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    baseline = speak("testing one two three").size
    rate_180 = speak("[:rate 180] testing one two three").size
    rate_90 = speak("[:rate 90] testing one two three").size
    rate_360 = speak("[:rate 360] testing one two three").size
    rate_250 = speak("[:rate 250] testing one two three").size
    rate_100 = speak("[:rate 100] testing one two three").size

    # 1. [:rate 180] is the documented default; identical to no directive.
    assert rate_180 == baseline, (
        f"[:rate 180] should equal no-rate baseline; got {rate_180} vs {baseline}"
    )

    # 2. Strict monotonicity: bigger WPM => shorter audio.
    assert rate_100 > rate_180 > rate_250 > rate_360, (
        f"Sample counts should be strictly decreasing as WPM grows; got "
        f"100→{rate_100} 180→{rate_180} 250→{rate_250} 360→{rate_360}"
    )

    # 3. Half-speed roughly doubles the audio (within ±25% — the
    # phoneme-duration table interpolation isn't perfectly linear and
    # picks up the same per-clause silence pad regardless of WPM, but
    # it's close enough that we can sanity-check direction + magnitude
    # without depending on exact PH-stage parity).
    assert 1.5 * baseline < rate_90 < 2.5 * baseline, (
        f"[:rate 90] should be ~2x baseline; got {rate_90} vs {baseline}"
    )

    # 4. Double-speed roughly halves it.
    assert 0.35 * baseline < rate_360 < 0.75 * baseline, (
        f"[:rate 360] should be ~0.5x baseline; got {rate_360} vs {baseline}"
    )

    # 5. The headline issue-#70 prompt: [:rate 250] on "testing one
    # two three". The Python full pipeline still has a substantial
    # absolute drift vs the C oracle (PH-stage timing + trailing-
    # silence pad — see docs/parity-divergence-audit.md and the more
    # recent trailing-silence work), but the *relative* scaling
    # against baseline should match the C oracle's 14697/19099 ≈
    # 0.770 ratio to within ±10%. Before issue #70, this ratio was
    # 5940/19140 ≈ 0.310 — off by a factor of 2.5x. After: pass.
    c_baseline = 19099
    c_rate_250 = 14697
    c_ratio = c_rate_250 / c_baseline  # ≈ 0.770
    py_ratio = rate_250 / baseline
    assert abs(py_ratio - c_ratio) < 0.10, (
        f"[:rate 250]/baseline ratio should match C's "
        f"{c_rate_250}/{c_baseline}={c_ratio:.3f} to within 10%; "
        f"got py={rate_250}/{baseline}={py_ratio:.3f} "
        f"(delta={py_ratio - c_ratio:+.3f})"
    )


def test_inline_rate_clamps_to_legal_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out-of-range ``[:rate N]`` is clamped to [75, 600], not rejected.

    Matches the C binary (and the documented bounds in
    :mod:`dectalk.cmd.cmd_states`). After clamping, ``[:rate 10]``
    should produce the same audio as ``[:rate 75]`` and ``[:rate 1000]``
    the same as ``[:rate 600]``.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    very_slow = speak("[:rate 10] hi").size
    min_rate = speak("[:rate 75] hi").size
    assert very_slow == min_rate

    very_fast = speak("[:rate 1000] hi").size
    max_rate = speak("[:rate 600] hi").size
    assert very_fast == max_rate


def test_capitalisation_is_irrelevant() -> None:
    a = text_to_phonemes("Hello World")
    b = text_to_phonemes("hello world")
    c = text_to_phonemes("HELLO WORLD")
    assert a == b == c


# -- DECTALK_FULL_PIPELINE gate --------------------------------------------


def test_full_pipeline_gate_produces_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    """``DECTALK_FULL_PIPELINE=1`` walks the whole translated PH stack.

    Tokenize -> ARPABET -> US allophone codes -> ``DphT`` populate ->
    ``init_phclause`` -> ``init_timing`` -> ``phinton`` -> per-frame
    driver loop (advancing ``nphone``/``tcum`` and calling
    ``phsettar`` + ``phdraw`` per frame) -> parstochip → LLFrame
    adapter -> hlsyn ``ll_synthesize``. The result is int16 PCM.
    Bit-parity with the C oracle is not asserted here -- that is
    a separate, multi-week gate guarded by the ``c_oracle`` marker.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    samples = _speak_via_python(
        text="hello world",
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert samples.size > 0


def test_full_pipeline_gate_short_circuits_for_empty_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty/un-tokenizable input returns zero samples (no phsettar walk)."""
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    samples = _speak_via_python(
        text="",
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert len(samples) == 0


def test_full_pipeline_gate_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``DECTALK_FULL_PIPELINE=1``, the legacy path runs.

    Tests that the gate is truly opt-in: with the env var unset, the
    legacy approximate pipeline produces samples without raising.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.delenv("DECTALK_FULL_PIPELINE", raising=False)
    samples = _speak_via_python(
        text="hello",
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert len(samples) > 0


def test_pump_frames_to_samples_empty_returns_zero() -> None:
    """``_pump_frames_to_samples([], None)`` short-circuits to zero samples."""
    out = _pump_frames_to_samples([], None)
    assert len(out) == 0


def _pump_with_canned_samples(
    monkeypatch: pytest.MonkeyPatch,
    canned: NDArray[np.int16],
    vol_att: int = 100,
) -> NDArray[np.int16]:
    """Drive ``_pump_frames_to_samples`` with a stubbed ``ll_synthesize``.

    The real ``ll_synthesize`` requires a fully-initialised resonator
    state (frames produced by the full PH pipeline), which is heavier
    than this unit-level test needs. Monkeypatching it to write a
    canonical waveform lets us assert just the post-scale arithmetic.

    Returns the resulting samples after the ``vol_att`` post-scale.
    """
    from dectalk.hlsyn import synthesize as synthesize_mod  # noqa: PLC0415
    from dectalk.hlsyn.llsyn import LLFrame  # noqa: PLC0415

    # ll_synthesize signature: (synth, frame, wave) -> int. The pump
    # passes a per-frame slice of ``wave``; tile our canned samples
    # over each frame slot. Tiling (rather than truncation) means we
    # exercise the multiply across a known, non-degenerate waveform
    # regardless of the speaker's UI (samples-per-frame) value.
    def fake_ll_synth(_synth: object, _frame: object, wave: NDArray[np.int16]) -> int:
        tiled = np.tile(canned, (len(wave) + len(canned) - 1) // len(canned))
        wave[:] = tiled[: len(wave)]
        return 0

    monkeypatch.setattr(synthesize_mod, "ll_synthesize", fake_ll_synth)
    # Also patch the binding in dectalk.api.speak, which is the
    # call site (the lazy import binds a local name).
    import dectalk.api.speak as speak_mod  # noqa: PLC0415

    # _pump_frames_to_samples does ``from dectalk.hlsyn.synthesize
    # import ll_synthesize`` inside the function body, so patching the
    # module attribute (above) covers the lookup. Sanity-check the
    # original import path is consistent.
    assert speak_mod is not None  # keeps the import alive for the patch.
    # Pass two LLFrame objects so the per-frame loop iterates twice.
    frames: list[object] = [LLFrame(), LLFrame()]
    return _pump_frames_to_samples(frames, None, vol_att=vol_att)


def test_pump_frames_vol_att_default_unity(monkeypatch: pytest.MonkeyPatch) -> None:
    """``vol_att = 100`` (the C kernel default) is unity Q15 within 1 LSB.

    ``int_volume_table[100] = 32767`` and Q15 unity is 32768, so the
    post-scale ``(out * 32767) >> 15`` is the identity to within 1 LSB
    of round-down. The no-op early-return in ``_pump_frames_to_samples``
    triggers when ``vol_mul == 32767``, so the default call returns
    the synth output unmodified.
    """
    # Use a known waveform: a small sinusoid-ish ramp.
    canned = np.array([1000, 2000, 3000, 4000, -1000, -2000, -3000, -4000], dtype=np.int16)
    out = _pump_with_canned_samples(monkeypatch, canned, vol_att=100)
    # At least one full canned waveform copy fits per frame; the first
    # ``len(canned)`` samples of each frame slot should equal canned.
    assert np.array_equal(out[: len(canned)], canned)


def test_pump_frames_vol_att_zero_silences_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """``vol_att = 0`` mutes the output (``int_volume_table[0] = 0``).

    Mirrors vtm3.c's behaviour when the kernel volume is set to the
    minimum: every sample multiplies by 0 and the output is
    bit-exactly silent.
    """
    canned = np.array([1000, 2000, 3000, -3000, -2000, -1000], dtype=np.int16)
    out = _pump_with_canned_samples(monkeypatch, canned, vol_att=0)
    assert int(np.max(np.abs(out))) == 0


def test_pump_frames_vol_att_below_unity_attenuates(monkeypatch: pytest.MonkeyPatch) -> None:
    """``vol_att < 100`` scales every sample by ``int_volume_table[vol_att] / 32768``.

    ``int_volume_table[50] = 5826``; verify the per-sample multiply
    matches the C ``frac1mul(out, vol_att)`` = ``(out * 5826) >> 15``.
    """
    from dectalk.vtm.volume_table import int_volume_table  # noqa: PLC0415

    canned = np.array([1000, 2000, 3000, -3000, -2000, -1000], dtype=np.int16)
    out = _pump_with_canned_samples(monkeypatch, canned, vol_att=50)
    vol_mul = int_volume_table[50]
    expected = ((canned.astype(np.int32) * vol_mul) >> 15).astype(np.int16)
    assert np.array_equal(out[: len(canned)], expected)


def test_pump_frames_vol_att_clamps_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """``vol_att`` outside ``[0, 140]`` clamps to the table range.

    Matches vtm3.c lines 515-518 which clamp ``pKsd_t->vol_att`` before
    indexing ``int_volume_table[]``. Negative values clamp to 0 (mute);
    values above 140 clamp to 140 (the table's maximum entry).
    """
    canned = np.array([1000, 2000, 3000, -1000, -2000, -3000], dtype=np.int16)
    neg = _pump_with_canned_samples(monkeypatch, canned, vol_att=-99)
    zero = _pump_with_canned_samples(monkeypatch, canned, vol_att=0)
    assert np.array_equal(neg, zero)

    huge = _pump_with_canned_samples(monkeypatch, canned, vol_att=999)
    max_idx = _pump_with_canned_samples(monkeypatch, canned, vol_att=140)
    assert np.array_equal(huge, max_idx)


def test_ksd_t_vol_att_default_matches_c_kernel() -> None:
    """``KsdT.vol_att`` defaults to 100 to mirror the C kernel.

    Documented in ``ttsapi.c`` lines 2050 / 6609:
    ``pKsd_t->vol_att=100;`` is the value set at every full kernel
    reset, and ``int_volume_table[100] = 32767`` (unity Q15 within
    1 LSB), so the default-volume path is ~no-op.
    """
    from dectalk.kernel.ksd_t import KsdT  # noqa: PLC0415

    assert KsdT().vol_att == 100


def test_assertiveness_loaded_for_us_paul(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #122 — ``pDph_t.assertiveness`` is non-zero after the
    Python full-pipeline per-clause init for US-Paul.

    The C bridge (``phram.c``) loads
    ``pDph_t->assertiveness = pDph_t->curspdef[SPD_AS] * 41``; with
    Paul's AS = 100 the result is 4100 (just above Q12 unity = 4096
    = full final F0 fall). Three ``frac4mul(..., assertiveness)``
    calls in ``phinton`` Rules 3/4/6 zero out the final-fall
    magnitude when this field is 0, masking every Rule 6 final-fall
    event in traces (``tar=0``).

    This test captures the post-load ``DphT`` by monkey-patching
    ``init_timing`` (the call that immediately follows the SPDEF
    loads in ``_render_clause_full``) and asserts the field is
    non-zero — and specifically 4100 for the default US-Paul row
    of ``p_us_vdf_dectalk43.c``.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    # Resolve the *current* init_timing module from sys.modules. Other tests
    # in the suite (e.g. test_ph_setallofeats_parity.py) intentionally purge
    # dectalk modules from sys.modules and re-import them, which leaves a
    # top-level ``from dectalk.ph import init_timing`` binding pointing at a
    # stale module object whose attributes won't be picked up by the
    # post-purge lazy ``from dectalk.ph.init_timing import init_timing``
    # inside ``_render_clause_full``. Importing fresh here keeps the spy
    # effective regardless of test ordering.
    fresh_init_timing = importlib.import_module("dectalk.ph.init_timing")

    captured: list[int] = []
    real_init_timing = fresh_init_timing.init_timing

    def _spy_init_timing(
        p_dph_t: DphT,
        pst_phsettar: DphSettarSt,
        *,
        sprate_ref: list[int],
        lang_curr: int,
    ) -> None:
        captured.append(p_dph_t.assertiveness)
        real_init_timing(
            p_dph_t,
            pst_phsettar,
            sprate_ref=sprate_ref,
            lang_curr=lang_curr,
        )

    # _render_clause_full imports init_timing lazily inside the function,
    # so patch the source module (which the lazy import binds to).
    monkeypatch.setattr(fresh_init_timing, "init_timing", _spy_init_timing, raising=True)

    # Re-import speak the same way so the call below dispatches into the
    # post-purge module that ``fresh_init_timing`` was patched on.
    fresh_speak = importlib.import_module("dectalk.api.speak")
    _ = fresh_speak.speak("hello world")

    assert captured, "init_timing was not invoked by the full pipeline"
    assert all(v > 0 for v in captured), (
        f"pDph_t.assertiveness must be non-zero at init_timing time for "
        f"US-Paul (issue #122); captured: {captured}"
    )
    # AS = 100 (Paul) * 41 = 4100 (Q12-scale: just above 4096 = unity).
    assert captured[0] == 4100, (
        f"pDph_t.assertiveness should equal 100 * 41 = 4100 for US-Paul; got {captured[0]}"
    )
