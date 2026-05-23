"""Verify ``_render_clause_full`` threads voice scalars via :class:`Spdefs`.

Issue #164. Before this work, the orchestrator in
:func:`dectalk.api.speak._render_clause_full` hardcoded Paul's
voice-table values (``size_hat_rise=18``, ``scale_str_rise=32``,
``assertiveness=100*41``, ``f0_lp_filter=1500+15*40``,
``f0minimum=(100-12)*10``, ``f0scalefac=100*41``) so non-Paul voices
were synthesised with Paul's intonation envelope. The Spdefs threading
loads the per-voice row from :mod:`dectalk.ph.voice_definitions` and
seeds ``DphT`` with the documented C voice-table scalars.

The tests below exercise four representative voices:

- ``paul`` -- default; Spdefs values must equal the previously
  hardcoded constants (regression guard).
- ``betty`` -- female, high pitch (AP=208), wide range (PR=240), low
  assertiveness (AS=35), hat-rise HR=14.
- ``harry`` -- male, low pitch (AP=89), narrow range (PR=80),
  high assertiveness (AS=100).
- ``frank`` -- male, mid-pitch (AP=155), narrow range (PR=90), medium
  assertiveness (AS=65), unique BR=50.

Each test runs the full pipeline (``DECTALK_FULL_PIPELINE=1``,
``DECTALK_DISABLE_CAPI=1``) and instruments :class:`DphT` after init
to confirm the per-voice scalars made it onto the engine state.
"""

from __future__ import annotations

import numpy as np
import pytest

from dectalk.api.spdefs_struct import Spdefs
from dectalk.ph.voice_definitions import (
    VOICES_BY_NAME,
    spdefs_for_voice,
    voice_betty,
    voice_frank,
    voice_harry,
    voice_paul,
    voice_tuple_to_spdefs,
)

# --- Spdefs conversion helpers ---------------------------------------------


def test_voice_tuple_to_spdefs_paul() -> None:
    """Paul's row maps to an Spdefs with documented field values."""
    s = voice_tuple_to_spdefs(voice_paul)
    assert isinstance(s, Spdefs)
    # SEX=MALE, AP=100, PR=100, AS=100, QU=40, HR=18, SR=32 -- the
    # values that used to be hardcoded in _render_clause_full.
    assert s.sex == 1
    assert s.assertiveness == 100
    assert s.average_pitch == 100
    assert s.pitch_range == 100
    assert s.quickness == 40
    assert s.hat_rise == 18
    assert s.stress_rise == 32


def test_voice_tuple_to_spdefs_betty() -> None:
    """Betty's row maps to her documented C voice-table values."""
    s = voice_tuple_to_spdefs(voice_betty)
    # From voice_betty literal (mirrors p_us_vdf.c's betty[] init):
    # SEX=FEMALE, AS=35, AP=208, PR=240, QU=55, HR=14, SR=20.
    assert s.sex == 0
    assert s.assertiveness == 35
    assert s.average_pitch == 208
    assert s.pitch_range == 240
    assert s.quickness == 55
    assert s.hat_rise == 14
    assert s.stress_rise == 20


def test_voice_tuple_to_spdefs_harry() -> None:
    """Harry's row maps to his documented C voice-table values."""
    s = voice_tuple_to_spdefs(voice_harry)
    # From voice_harry literal: SEX=MALE, AS=100, AP=89, PR=80, QU=10,
    # HR=20, SR=30.
    assert s.sex == 1
    assert s.assertiveness == 100
    assert s.average_pitch == 89
    assert s.pitch_range == 80
    assert s.quickness == 10
    assert s.hat_rise == 20
    assert s.stress_rise == 30


def test_voice_tuple_to_spdefs_frank() -> None:
    """Frank's row maps to his documented C voice-table values."""
    s = voice_tuple_to_spdefs(voice_frank)
    # From voice_frank literal: SEX=MALE, AS=65, AP=155, PR=90, QU=0,
    # HR=20, SR=22.
    assert s.sex == 1
    assert s.assertiveness == 65
    assert s.average_pitch == 155
    assert s.pitch_range == 90
    assert s.quickness == 0
    assert s.hat_rise == 20
    assert s.stress_rise == 22


def test_spdefs_for_voice_default_is_paul() -> None:
    """``spdefs_for_voice(None)`` returns Paul's table."""
    assert spdefs_for_voice(None) == voice_tuple_to_spdefs(voice_paul)


def test_spdefs_for_voice_case_insensitive() -> None:
    """Voice name lookup is case-insensitive."""
    assert spdefs_for_voice("Betty") == voice_tuple_to_spdefs(voice_betty)
    assert spdefs_for_voice("HARRY") == voice_tuple_to_spdefs(voice_harry)


def test_spdefs_for_voice_unknown_falls_back_to_paul() -> None:
    """Unknown names fall back to Paul (not raised); public API validates names."""
    assert spdefs_for_voice("nonexistent") == voice_tuple_to_spdefs(voice_paul)


def test_voices_by_name_covers_public_presets() -> None:
    """Every public-API preset name has a row in VOICES_BY_NAME."""
    # Match the canonical voice-id set the public API exposes via
    # ``dectalk.data.voices.PRESETS``. Wendy and Willy share the same
    # C voice row (the only female-breathy tradition entry).
    expected_names = {
        "paul",
        "betty",
        "harry",
        "frank",
        "dennis",
        "kit",
        "ursula",
        "rita",
        "willy",
    }
    assert expected_names.issubset(VOICES_BY_NAME.keys())


# --- _render_clause_full threading -----------------------------------------


def _capture_dpht_after_init(
    voice: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> object:
    """Run ``_render_clause_full`` for ``voice`` and capture DphT post-init.

    Monkey-patches ``us_phtiming`` (the first call after all DphT
    scalar seeding completes in ``_render_clause_full``) to grab the
    DphT instance before any further mutation. Returns the captured
    state for inspection by the caller.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    import importlib  # noqa: PLC0415

    import dectalk.ph.us_phtiming as tim_mod  # noqa: PLC0415

    # ``import dectalk.api.speak`` resolves to the re-exported ``speak``
    # function in ``dectalk.api.__init__``; grab the module via
    # importlib so we can reach ``_render_clause_full`` on the module
    # object itself.
    speak_mod = importlib.import_module("dectalk.api.speak")

    captured: dict[str, object] = {}
    real_us_phtiming = tim_mod.us_phtiming

    def _capture(handle: object) -> object:  # pyright: ignore[reportUnusedFunction]
        captured["dph_t"] = handle.p_ph_thread_data  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        return real_us_phtiming(handle)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(tim_mod, "us_phtiming", _capture)
    if hasattr(speak_mod, "us_phtiming"):  # imported lazily, but be defensive.
        monkeypatch.setattr(speak_mod, "us_phtiming", _capture)

    samples = speak_mod._render_clause_full(  # type: ignore[attr-defined]
        "hello world",
        rate=1.0,
        voice=voice,
        lang="us",
        lts_fallback=True,
    )
    assert isinstance(samples, np.ndarray)
    assert samples.size > 0
    assert "dph_t" in captured, "us_phtiming was not invoked -- pipeline aborted early"
    return captured["dph_t"]


def test_render_clause_paul_matches_legacy_scalars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paul (default voice) preserves the previously hardcoded scalar values.

    Regression guard: the values that used to be bare literals in
    ``_render_clause_full`` must equal what the Spdefs threading
    produces for Paul.
    """
    dph_t = _capture_dpht_after_init(None, monkeypatch)
    assert dph_t.size_hat_rise == 18  # type: ignore[attr-defined]
    assert dph_t.scale_str_rise == 32  # type: ignore[attr-defined]
    assert dph_t.assertiveness == 100 * 41  # type: ignore[attr-defined]
    assert dph_t.f0_lp_filter == 1500 + 15 * 40  # type: ignore[attr-defined]
    assert dph_t.f0minimum == (100 - 12) * 10  # type: ignore[attr-defined]
    assert dph_t.f0scalefac == 100 * 41  # type: ignore[attr-defined]


def test_render_clause_betty_uses_betty_scalars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Betty (female, AP=208) gets her documented C voice-table values."""
    dph_t = _capture_dpht_after_init("betty", monkeypatch)
    # HR=14, SR=20, AS=35, QU=55, AP=208, PR=240 from voice_betty.
    assert dph_t.size_hat_rise == 14  # type: ignore[attr-defined]
    assert dph_t.scale_str_rise == 20  # type: ignore[attr-defined]
    assert dph_t.assertiveness == 35 * 41  # type: ignore[attr-defined]
    assert dph_t.f0_lp_filter == 1500 + 15 * 55  # type: ignore[attr-defined]
    assert dph_t.f0minimum == (208 - 12) * 10  # type: ignore[attr-defined]
    assert dph_t.f0scalefac == 240 * 41  # type: ignore[attr-defined]


def test_render_clause_harry_uses_harry_scalars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Harry (male, AP=89) gets his documented C voice-table values."""
    dph_t = _capture_dpht_after_init("harry", monkeypatch)
    # HR=20, SR=30, AS=100, QU=10, AP=89, PR=80 from voice_harry.
    assert dph_t.size_hat_rise == 20  # type: ignore[attr-defined]
    assert dph_t.scale_str_rise == 30  # type: ignore[attr-defined]
    assert dph_t.assertiveness == 100 * 41  # type: ignore[attr-defined]
    assert dph_t.f0_lp_filter == 1500 + 15 * 10  # type: ignore[attr-defined]
    assert dph_t.f0minimum == (89 - 12) * 10  # type: ignore[attr-defined]
    assert dph_t.f0scalefac == 80 * 41  # type: ignore[attr-defined]


def test_render_clause_frank_uses_frank_scalars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frank (male, AP=155) gets his documented C voice-table values."""
    dph_t = _capture_dpht_after_init("frank", monkeypatch)
    # HR=20, SR=22, AS=65, QU=0, AP=155, PR=90 from voice_frank.
    assert dph_t.size_hat_rise == 20  # type: ignore[attr-defined]
    assert dph_t.scale_str_rise == 22  # type: ignore[attr-defined]
    assert dph_t.assertiveness == 65 * 41  # type: ignore[attr-defined]
    assert dph_t.f0_lp_filter == 1500 + 15 * 0  # type: ignore[attr-defined]
    assert dph_t.f0minimum == (155 - 12) * 10  # type: ignore[attr-defined]
    assert dph_t.f0scalefac == 90 * 41  # type: ignore[attr-defined]


def test_render_clause_distinct_voices_produce_distinct_f0_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paul/Betty/Harry/Frank land on distinct (AP, PR) tuples on DphT.

    Sanity check: the four voices have different AP and PR rows, so
    their derived ``f0minimum`` / ``f0scalefac`` seeds must differ. If
    one of them collapses to Paul's value the threading regressed.
    """
    f0_seeds: set[tuple[int, int]] = set()
    for name in ("paul", "betty", "harry", "frank"):
        mp = pytest.MonkeyPatch()
        try:
            dph_t = _capture_dpht_after_init(None if name == "paul" else name, mp)
            f0_seeds.add((dph_t.f0minimum, dph_t.f0scalefac))  # type: ignore[attr-defined]
        finally:
            mp.undo()
    assert len(f0_seeds) == 4, f"expected 4 distinct (f0min, f0scale) tuples, got {f0_seeds}"
    _ = monkeypatch  # silence unused-arg lint; the fixture is provided per-call above.
