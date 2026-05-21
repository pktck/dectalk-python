"""Verify ``us_phtiming`` produces sane per-allophone durations.

The function ports ~1100 active lines of duration-rule logic from
``src/dapi/src/ph/p_us_tim.c``. These tests pin the function-level
contract: every non-silence allophone gets a positive frame
duration, slow speech yields longer durations than fast speech, and
the speaking-rate scaling factors flow through correctly.
"""

# ruff: noqa: N806 -- preserve C-source mixedCase identifiers (pDph_t, pKsd_t)

from __future__ import annotations

from typing import cast

from dectalk.include.usp_codes import (
    USP_AX,
    USP_D,
    USP_EH,
    USP_HX,
    USP_LL,
    USP_OW,
    USP_R,
    USP_W,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.init_phclause import init_phclause
from dectalk.ph.init_timing import init_timing
from dectalk.ph.numeric_constants import NSAMP_FRAME
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_phtiming import us_phtiming
from dectalk.ph.utterance_constants import GEN_SIL


def _build_state(allophons: list[int], *, sprate: int = 180) -> TtsHandle:
    """Construct a TtsHandle ready for ``us_phtiming``.

    Mirrors :func:`dectalk.api.speak._speak_via_python_full`'s
    setup so the test exercises the same wiring path.
    """
    nallotot = len(allophons)
    pDph_t = DphT()
    pDph_t.allophons = list(allophons)
    pDph_t.allofeats = [0] * nallotot
    pDph_t.allodurs = [0] * nallotot
    pDph_t.nallotot = nallotot
    pDph_t.sprate = sprate
    pDph_t.number_words = 2
    settar = DphSettarSt()
    settar.initsw = 1
    pDph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = pDph_t
    pKsd_t = KsdT()
    pKsd_t.sprate = sprate
    pKsd_t.lang_curr = LANG_english
    handle.p_kernel_share_data = pKsd_t

    # init_phclause writes allodurs/allophons/allofeats with the
    # SAFETY-padded size and zero-fills user_durs. We then overwrite
    # allophons / nallotot with our test values so the function walks
    # the right phones; user_durs stays at zero (no override).
    init_phclause(pDph_t)
    pDph_t.allophons[:nallotot] = list(allophons)
    pDph_t.allofeats[:nallotot] = [0] * nallotot
    pDph_t.nallotot = nallotot

    init_timing(
        pDph_t,
        settar,
        sprate_ref=[sprate],
        lang_curr=LANG_english,
    )
    return handle


def _hello_world_allophones() -> list[int]:
    """A 'hello world'-ish allophone stream sandwiched in silence.

    Roughly: SIL h-e-l-o w-r-l-d SIL. The exact ARPABET-to-US-allophone
    mapping isn't important here -- we just need a stream the duration
    rules can chew on.
    """
    return [
        GEN_SIL,
        USP_HX,
        USP_EH,
        USP_LL,
        USP_OW,
        USP_W,
        USP_R,
        USP_LL,
        USP_D,
        GEN_SIL,
    ]


def test_every_non_silence_phone_gets_positive_duration() -> None:
    """The named output of us_phtiming is allodurs[]; non-silence > 0."""
    allophons = _hello_world_allophones()
    handle = _build_state(allophons, sprate=180)

    us_phtiming(handle)

    pDph_t = cast(DphT, handle.p_ph_thread_data)
    for i, phon in enumerate(allophons):
        if phon == GEN_SIL:
            continue
        assert pDph_t.allodurs[i] > 0, (
            f"non-silence phone {phon!r} at index {i} got "
            f"allodurs={pDph_t.allodurs[i]}; expected > 0"
        )


def test_slower_sprate_yields_longer_durations() -> None:
    """A slower speaking rate should stretch overall clause duration.

    The mechanism: ``init_timing`` writes a larger ``sprat2`` for slow
    rates, and ``us_phtiming`` scales every ``durxx`` by ``sprat2``.
    """
    allophons = _hello_world_allophones()

    fast_handle = _build_state(allophons, sprate=300)
    slow_handle = _build_state(allophons, sprate=120)

    us_phtiming(fast_handle)
    us_phtiming(slow_handle)

    fast_state = cast(DphT, fast_handle.p_ph_thread_data)
    slow_state = cast(DphT, slow_handle.p_ph_thread_data)

    fast_total = sum(fast_state.allodurs[i] for i, phon in enumerate(allophons) if phon != GEN_SIL)
    slow_total = sum(slow_state.allodurs[i] for i, phon in enumerate(allophons) if phon != GEN_SIL)

    assert slow_total > fast_total, (
        f"slow (sprate=120) total frames {slow_total} not greater than "
        f"fast (sprate=300) total frames {fast_total}"
    )


def test_silence_durations_are_positive() -> None:
    """Even silence frames get a duration (the inter-clause pause)."""
    allophons = _hello_world_allophones()
    handle = _build_state(allophons, sprate=180)
    us_phtiming(handle)

    pDph_t = cast(DphT, handle.p_ph_thread_data)
    # The initial silence pause should be at least 2 frames (the C
    # source clamps with `if (dpause < 2) dpause = 2`).
    assert pDph_t.allodurs[0] >= 2


def test_longcumdur_accumulates_across_phones() -> None:
    """``longcumdur`` is the sum of ``durxx * NSAMP_FRAME``."""
    allophons = _hello_world_allophones()
    handle = _build_state(allophons, sprate=180)
    us_phtiming(handle)

    pDph_t = cast(DphT, handle.p_ph_thread_data)
    expected = sum(d * NSAMP_FRAME for d in pDph_t.allodurs[: len(allophons)])
    assert pDph_t.longcumdur == expected


def test_single_vowel_clause_runs_without_error() -> None:
    """Single-vowel + silence boundary doesn't trigger any IndexError.

    Regression guard for the various ``allophons[nphon + 2]`` /
    ``allophons[nphon + 1]`` lookups in the rule body.
    """
    allophons = [GEN_SIL, USP_AX, GEN_SIL]
    handle = _build_state(allophons, sprate=180)

    us_phtiming(handle)

    pDph_t = cast(DphT, handle.p_ph_thread_data)
    assert pDph_t.allodurs[1] > 0
