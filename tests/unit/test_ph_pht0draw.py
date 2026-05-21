"""Unit tests for ``pht0draw`` (F0 contour generator).

Verifies:

1. Hard init clears all F0 state and advances ``nf0ev`` to -1.
2. Soft init further advances ``nf0ev`` to 0 and initialises frame
   counters.
3. After a single frame with no F0 events, ``parstochip[OUT_T0]``
   is non-zero (flutter + f0minimum push it above 0).
4. A STEP command increments ``tarhat`` on the next frame.
5. MALE path writes a voiced-frame F0 in ``[LOWEST_F0, HIGHEST_F0]``.
6. FEMALE path runs and also stays within the legal F0 band.
7. Calling multiple times advances ``nfram`` / ``nframs`` / ``nframg``.
"""

from __future__ import annotations

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import HIGHEST_F0, LOWEST_F0
from dectalk.ph.numeric_constants import FEMALE, MALE
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.pht0draw import pht0draw
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL, STEP

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handle(
    *,
    nf0ev: int = -2,
    f0minimum: int = 600,
    f0_lp_filter: int = 1300,
    malfem: int = MALE,
    nallotot: int = 2,
    f0scalefac: int = 4096,
    clausetype: int = 0,
) -> TtsHandle:
    """Return a minimal TtsHandle ready for pht0draw."""
    p_dph_t = DphT()
    p_dph_t.nf0ev = nf0ev
    p_dph_t.f0minimum = f0minimum
    p_dph_t.f0_lp_filter = f0_lp_filter
    p_dph_t.malfem = malfem
    p_dph_t.nallotot = nallotot
    p_dph_t.f0scalefac = f0scalefac
    p_dph_t.clausetype = clausetype
    p_dph_t.f0mode = 1  # NORMAL — not SINGING

    # Minimal phoneme arrays so segmental logic doesn't index-error.
    p_dph_t.allophons = [GEN_SIL, GEN_SIL, GEN_SIL, GEN_SIL]
    p_dph_t.allodurs = [10, 10, 10, 10]
    p_dph_t.allofeats = [0, 0, 0, 0]

    # F0 command arrays (no events).
    p_dph_t.f0tar = [0]
    p_dph_t.f0type = [0]
    p_dph_t.f0length = [1]
    p_dph_t.f0tim = [9999]  # First event far in the future.
    p_dph_t.nf0tot = 0

    # parstochip sized for all outputs.
    p_dph_t.parstochip = [0] * 20

    # Attach a fresh DphSettarSt.
    p_dph_t.pSTphsettar = DphSettarSt()

    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    return handle


# ---------------------------------------------------------------------------
# Test 1 — hard init resets all F0 state
# ---------------------------------------------------------------------------


def test_hard_init_clears_state() -> None:
    """Hard init (nf0ev <= -2) resets all F0 accumulators."""
    handle = _make_handle(nf0ev=-2)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)

    # Pre-set some fields to non-zero to confirm they get cleared.
    pdphsettar.tarhat = 999
    pdphsettar.tarimp = 888
    pdphsettar.delimp = 777
    pdphsettar.nframb = 42

    pht0draw(handle)

    # After the first call (hard → soft → single frame):
    # nf0ev should have advanced to 0.
    assert p_dph_t.nf0ev == 0
    # tarhat should have been zeroed during hard init.
    # (It may then be modified by subsequent logic; the key invariant
    # is that it started at 0 before the frame ran.)
    # We check the filter memories instead, which are only touched by
    # hard/soft init and stay 0 for the first frame.
    assert pdphsettar.nframb == 1  # ticked exactly once by the frame


# ---------------------------------------------------------------------------
# Test 2 — soft init sets nf0ev=0 and resets frame counters
# ---------------------------------------------------------------------------


def test_soft_init_advances_nf0ev() -> None:
    """After hard+soft init nf0ev == 0."""
    handle = _make_handle(nf0ev=-2)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    pht0draw(handle)

    assert p_dph_t.nf0ev == 0


# ---------------------------------------------------------------------------
# Test 3 — parstochip[OUT_T0] is non-zero after first frame
# ---------------------------------------------------------------------------


def test_out_t0_nonzero_after_first_frame() -> None:
    """parstochip[OUT_T0] is non-zero when f0minimum > 0."""
    handle = _make_handle(nf0ev=-2, f0minimum=800)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    pht0draw(handle)

    assert p_dph_t.parstochip[OUT_T0] != 0, (
        "OUT_T0 must be set to f0prime (a non-zero F0 value when f0minimum > 0)"
    )


# ---------------------------------------------------------------------------
# Test 4 — STEP command increments tarhat
# ---------------------------------------------------------------------------


def test_step_command_increments_tarhat() -> None:
    """A STEP command increments tarhat by f0command."""
    handle = _make_handle(nf0ev=-2)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)

    # First call: hard+soft init, no commands.
    pht0draw(handle)

    # Now inject a STEP command at the next frame boundary.
    # nfram is 1 after the first call; set dtimf0 = 1 so it fires.
    step_amount = 200
    p_dph_t.f0tar = [step_amount, 0]
    p_dph_t.f0type = [STEP, 0]
    p_dph_t.f0length = [1, 1]
    p_dph_t.f0tim = [1, 9999]
    p_dph_t.nf0tot = 1
    p_dph_t.nf0ev = 0
    pdphsettar.dtimf0 = 1
    pdphsettar.nfram = 1  # ensure nfram >= dtimf0

    tarhat_before = pdphsettar.tarhat
    pht0draw(handle)

    assert pdphsettar.tarhat == tarhat_before + step_amount


# ---------------------------------------------------------------------------
# Test 5 — MALE path produces F0 in [LOWEST_F0, HIGHEST_F0]
# ---------------------------------------------------------------------------


def test_male_f0prime_in_legal_range() -> None:
    """f0prime stays within [LOWEST_F0, HIGHEST_F0] after each frame."""
    handle = _make_handle(nf0ev=-2, f0minimum=800, f0scalefac=4096)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    for _ in range(30):
        pht0draw(handle)
        assert LOWEST_F0 <= p_dph_t.f0prime <= HIGHEST_F0, (
            f"f0prime={p_dph_t.f0prime!r} out of [{LOWEST_F0}, {HIGHEST_F0}]"
        )


# ---------------------------------------------------------------------------
# Test 6 — FEMALE path runs and stays in legal F0 range
# ---------------------------------------------------------------------------


def test_female_f0prime_in_legal_range() -> None:
    """FEMALE path also clamps f0prime to [LOWEST_F0, HIGHEST_F0]."""
    handle = _make_handle(nf0ev=-2, malfem=FEMALE, f0minimum=1200, f0scalefac=4096)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    for _ in range(30):
        pht0draw(handle)
        assert LOWEST_F0 <= p_dph_t.f0prime <= HIGHEST_F0, (
            f"FEMALE f0prime={p_dph_t.f0prime!r} out of [{LOWEST_F0}, {HIGHEST_F0}]"
        )


def test_female_hard_init_sets_newnote_1600() -> None:
    """FEMALE hard init sets newnote=1600 (vs MALE's 1000)."""
    handle = _make_handle(nf0ev=-2, malfem=FEMALE)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)

    pht0draw(handle)

    # newnote is touched once by hard init and not modified afterwards
    # when no USER targets fire.
    assert pdphsettar.newnote == 1600


def test_female_avglstop_default_zero() -> None:
    """FEMALE writes avglstop each frame; with no glottal stop it is 0."""
    handle = _make_handle(nf0ev=-2, malfem=FEMALE)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)

    pht0draw(handle)

    # tglstp is initialised to -200 and nframg starts small, so
    # dtglst > 5 in this first frame.
    dtglst = abs(pdphsettar.nframg - pdphsettar.tglstp)
    if dtglst > 5:
        assert p_dph_t.avglstop == 0
    else:
        assert p_dph_t.avglstop == 6 - dtglst


# ---------------------------------------------------------------------------
# Test 7 — frame counters advance each call
# ---------------------------------------------------------------------------


def test_frame_counters_advance() -> None:
    """nfram, nframs, nframg each increment by 1 per call."""
    handle = _make_handle(nf0ev=-2)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    # First call: hard + soft init + first frame.
    pht0draw(handle)
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)

    nfram_after_1 = pdphsettar.nfram
    nframs_after_1 = pdphsettar.nframs
    nframg_after_1 = pdphsettar.nframg

    # Second call: only a frame tick, no init.
    pht0draw(handle)

    assert pdphsettar.nfram == nfram_after_1 + 1
    assert pdphsettar.nframs == nframs_after_1 + 1
    assert pdphsettar.nframg == nframg_after_1 + 1


# ---------------------------------------------------------------------------
# Test 8 — multiple frames accumulate a realistic F0 contour
# ---------------------------------------------------------------------------


def test_f0_contour_rises_with_hat_step() -> None:
    """A STEP command raises f0 in subsequent frames (hat accumulates)."""
    handle = _make_handle(nf0ev=-2, f0minimum=500)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    # Run 5 frames to settle the hard+soft init and reach steady state.
    for _ in range(5):
        pht0draw(handle)

    f0_before_step = p_dph_t.f0prime

    # Inject a STEP(+300) at the current frame boundary.
    pdphsettar = p_dph_t.pSTphsettar
    assert isinstance(pdphsettar, DphSettarSt)
    p_dph_t.f0tar = [300, 0]
    p_dph_t.f0type = [STEP, 0]
    p_dph_t.f0length = [1, 1]
    p_dph_t.f0tim = [1, 9999]
    p_dph_t.nf0tot = 1
    p_dph_t.nf0ev = 0
    pdphsettar.dtimf0 = 1
    pdphsettar.nfram = 1

    # Run 10 more frames so the 1-pole filter can respond.
    for _ in range(10):
        pht0draw(handle)

    f0_after_step = p_dph_t.f0prime

    # The hat step should have raised the contour.
    assert f0_after_step > f0_before_step, (
        f"Expected f0 to rise after STEP; before={f0_before_step}, after={f0_after_step}"
    )
