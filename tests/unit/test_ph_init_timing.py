"""Verify init_timing matches ph_timng.c."""

from __future__ import annotations

from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
)
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.init_timing import init_timing
from dectalk.ph.numeric_constants import FRAC_ONE


def test_zeroes_longcumdur_on_every_call() -> None:
    """``longcumdur`` is unconditionally reset to 0."""
    state = DphT()
    settar = DphSettarSt()
    state.longcumdur = 999
    init_timing(state, settar, sprate_ref=[180], lang_curr=LANG_english)
    assert state.longcumdur == 0


def test_english_normal_rate_180() -> None:
    """sprate=180 → sprat0=180, sprat1=FRAC_ONE, sprat2=FRAC_ONE."""
    state = DphT()
    settar = DphSettarSt()
    init_timing(state, settar, sprate_ref=[180], lang_curr=LANG_english)
    assert settar.sprat0 == 180
    # sprat0 = 180: sprat1 = muldv(FRAC_ONE, 400-180, 220) = muldv(16384, 220, 220) = 16384
    assert settar.sprat1 == FRAC_ONE
    # sprat0 = 180: sprat2 = (sprat1+FRAC_ONE)/2 = (16384+16384)/2 = 16384
    assert settar.sprat2 == FRAC_ONE
    assert state.timeref == 16000 // 180


def test_english_fast_rate_300() -> None:
    """sprate=300 → sprat0 linearised to 275."""
    state = DphT()
    settar = DphSettarSt()
    init_timing(state, settar, sprate_ref=[300], lang_curr=LANG_english)
    # 300 > 250 → sprat0 = 250 + (50 >> 1) = 275
    assert settar.sprat0 == 275


def test_english_slow_rate_120() -> None:
    """sprate=120 → sprat0=120, sprat1 ≈ 1.5*FRAC_ONE."""
    state = DphT()
    settar = DphSettarSt()
    init_timing(state, settar, sprate_ref=[120], lang_curr=LANG_english)
    assert settar.sprat0 == 120
    # sprat0 = 120 (< 180): temp2 = 300-120 = 180, temp3 = 120.
    # sprat1 = muldv(16384, 180, 120) = 24576 (= 1.5 * 16384)
    assert settar.sprat1 == 24576


def test_no_op_when_sprate_matches_sprlast() -> None:
    """When sprate hasn't changed, only longcumdur is reset."""
    state = DphT()
    settar = DphSettarSt()
    settar.sprlast = 180
    settar.sprat0 = 99  # Sentinel; should be untouched.
    settar.sprat1 = 99
    settar.sprat2 = 99
    state.timeref = 99
    state.longcumdur = 42
    init_timing(state, settar, sprate_ref=[180], lang_curr=LANG_english)
    assert settar.sprat0 == 99
    assert settar.sprat1 == 99
    assert settar.sprat2 == 99
    assert state.timeref == 99
    assert state.longcumdur == 0  # Always reset.


def test_updates_sprlast_after_recompute() -> None:
    """sprlast gets the (possibly-adjusted) sprate after compute."""
    state = DphT()
    settar = DphSettarSt()
    init_timing(state, settar, sprate_ref=[200], lang_curr=LANG_english)
    assert settar.sprlast == 200


def test_british_adjusts_sprate_by_plus_20() -> None:
    """UK English bumps sprate by 20 before timeref calc."""
    state = DphT()
    settar = DphSettarSt()
    sprate_ref = [180]
    init_timing(state, settar, sprate_ref=sprate_ref, lang_curr=LANG_british)
    assert sprate_ref[0] == 200
    assert state.timeref == 16000 // 200


def test_latin_american_uses_4000_constant() -> None:
    """Latin American uses 4000/sprate (vs 16000 for English)."""
    state = DphT()
    settar = DphSettarSt()
    sprate_ref = [200]
    init_timing(state, settar, sprate_ref=sprate_ref, lang_curr=LANG_latin_american)
    assert sprate_ref[0] == 235
    assert state.timeref == 4000 // 235


def test_german_uses_12000_constant() -> None:
    """German uses 12000/sprate; sprate bumps after timeref."""
    state = DphT()
    settar = DphSettarSt()
    sprate_ref = [200]
    init_timing(state, settar, sprate_ref=sprate_ref, lang_curr=LANG_german)
    # Timeref uses pre-bump sprate (200), then sprate becomes 230.
    assert state.timeref == 12000 // 200
    assert sprate_ref[0] == 230


def test_french_clamps_to_120_350() -> None:
    """French clamps sprate-20 to [120, 350]."""
    state = DphT()
    settar = DphSettarSt()
    sprate_ref = [100]
    init_timing(state, settar, sprate_ref=sprate_ref, lang_curr=LANG_french)
    # 100 - 20 = 80, clamped up to 120.
    assert sprate_ref[0] == 120
    sprate_ref = [500]
    init_timing(state, settar, sprate_ref=sprate_ref, lang_curr=LANG_french)
    # 500 - 20 = 480, clamped down to 350.
    assert sprate_ref[0] == 350


def test_sprat1_clamped_to_1_when_negative() -> None:
    """When temp2 would be negative, the C source clamps it to 1."""
    state = DphT()
    settar = DphSettarSt()
    # sprate = 500 → sprat0 = 250 + (250>>1) = 375.
    # sprat0 >= 180: temp2 = 400 - 375 = 25. (Still positive.)
    # Test instead with a higher rate that would make temp2 negative:
    # sprate = 550 → sprat0 = 250 + (300>>1) = 400.
    # sprat0 >= 180: temp2 = 400 - 400 = 0 — clamped to 1.
    init_timing(state, settar, sprate_ref=[550], lang_curr=LANG_english)
    # sprat1 = muldv(FRAC_ONE, 1, 220) = 16384 // 220 = 74
    assert settar.sprat1 == 74
