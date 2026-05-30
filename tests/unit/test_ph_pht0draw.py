"""Unit tests for ``pht0draw`` (F0 contour generator, ph_drwt01.c).

The production build is a single function (no MALE/FEMALE split). These
exercise the per-frame behaviour:

1. Hard + soft init advance ``nf0ev`` to 0 and prime the 2-pole filter
   memories to the declination baseline.
2. ``parstochip[OUT_T0]`` is a non-zero pitch period after the first
   frame.
3. An even f0command STEP accumulates into ``tarhat``; an odd one is a
   doubled IMPULSE.
4. ``f0prime`` stays within ``[LOWEST_F0, HIGHEST_F0]`` every frame.
5. Frame counters ``nfram`` / ``nframs`` / ``nframg`` advance each call.
6. A sustained hat STEP raises the rendered contour.
"""

from __future__ import annotations

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import F0SHFT, HIGHEST_F0, LOWEST_F0
from dectalk.ph.math_helpers import muldv
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.pht0draw import pht0draw
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL


def _make_handle(
    *,
    nf0ev: int = -2,
    f0minimum: int = 1100,
    f0_lp_filter: int = 1300,
    nallotot: int = 4,
    f0scalefac: int = 4096,
    f0basefall: int = 0,
) -> TtsHandle:
    """Return a minimal TtsHandle ready for pht0draw."""
    p = DphT()
    p.nf0ev = nf0ev
    p.f0minimum = f0minimum
    p.f0_lp_filter = f0_lp_filter
    p.f0basefall = f0basefall
    p.nallotot = nallotot
    p.f0scalefac = f0scalefac
    p.f0mode = 1  # NORMAL — not SINGING

    p.allophons = [GEN_SIL, GEN_SIL, GEN_SIL, GEN_SIL]
    p.allodurs = [10, 10, 10, 10]
    p.allofeats = [0, 0, 0, 0]

    p.f0tar = [0, 0]
    p.f0tim = [9999, 9999]  # first event far in the future
    p.nf0tot = 0

    p.parstochip = [0] * 20
    p.pSTphsettar = DphSettarSt()

    handle = TtsHandle()
    handle.p_ph_thread_data = p
    return handle


def _dph(handle: TtsHandle) -> DphT:
    p = handle.p_ph_thread_data
    assert isinstance(p, DphT)
    return p


def _settar(handle: TtsHandle) -> DphSettarSt:
    st = _dph(handle).pSTphsettar
    assert isinstance(st, DphSettarSt)
    return st


def test_init_advances_nf0ev_and_primes_filter() -> None:
    """Hard+soft init advance nf0ev to 0 and set the 2-pole coefficients."""
    handle = _make_handle()
    p = _dph(handle)
    st = _settar(handle)
    pht0draw(handle)
    assert p.nf0ev == 0
    # f0beginfall = 1070 (f0basefall == 0); coefficients loaded.
    assert st.f0beginfall == 1070
    assert st.f0a2 == 1300
    assert st.f0a1 == 1300 << F0SHFT


def test_out_t0_nonzero_after_first_frame() -> None:
    """parstochip[OUT_T0] is a valid non-zero period after the first frame."""
    handle = _make_handle()
    p = _dph(handle)
    pht0draw(handle)
    assert p.parstochip[OUT_T0] != 0
    assert p.parstochip[OUT_T0] == muldv(400, 1000, p.f0prime)


def test_even_command_accumulates_tarhat() -> None:
    """An even f0command is a STEP into ``tarhat``."""
    handle = _make_handle()
    p = _dph(handle)
    st = _settar(handle)
    pht0draw(handle)  # init

    p.f0tar = [200, 0]
    p.f0tim = [1, 9999]
    p.nf0tot = 1
    p.nf0ev = 0
    st.dtimf0 = 1
    st.nfram = 1
    before = st.tarhat
    pht0draw(handle)
    assert st.tarhat == before + 200


def test_odd_command_is_doubled_impulse() -> None:
    """An odd f0command is a doubled IMPULSE into ``tarimp``."""
    handle = _make_handle()
    p = _dph(handle)
    st = _settar(handle)
    pht0draw(handle)  # init

    p.f0tar = [151, 0]
    p.f0tim = [1, 9999]
    p.nf0tot = 1
    p.nf0ev = 0
    st.dtimf0 = 1
    st.nfram = 1
    pht0draw(handle)
    # tarimp = 151 + 151 = 302, then one frame of countdown leaves it set.
    assert st.tarimp == 302


def test_f0prime_in_legal_range() -> None:
    """f0prime stays within [LOWEST_F0, HIGHEST_F0] after each frame."""
    handle = _make_handle(f0minimum=800)
    p = _dph(handle)
    for _ in range(30):
        pht0draw(handle)
        assert LOWEST_F0 <= p.f0prime <= HIGHEST_F0


def test_avglstop_zero_when_far_from_glottal_stop() -> None:
    """avglstop is 0 each frame when no glottal stop is active."""
    handle = _make_handle()
    p = _dph(handle)
    for _ in range(5):
        pht0draw(handle)
        assert p.avglstop == 0


def test_frame_counters_advance() -> None:
    """nfram, nframs, nframg each increment by 1 per call."""
    handle = _make_handle()
    pht0draw(handle)
    st = _settar(handle)
    nfram, nframs, nframg = st.nfram, st.nframs, st.nframg
    pht0draw(handle)
    assert st.nfram == nfram + 1
    assert st.nframs == nframs + 1
    assert st.nframg == nframg + 1


def test_contour_rises_with_hat_step() -> None:
    """A sustained hat STEP raises the rendered contour."""
    handle = _make_handle(f0minimum=1100)
    p = _dph(handle)
    st = _settar(handle)
    for _ in range(5):
        pht0draw(handle)
    before = p.f0prime

    # Inject a STEP(+400) (even -> tarhat) and let the 2-pole respond.
    p.f0tar = [400, 0]
    p.f0tim = [1, 9999]
    p.nf0tot = 1
    p.nf0ev = 0
    st.dtimf0 = 1
    st.nfram = 1
    for _ in range(12):
        pht0draw(handle)
    after = p.f0prime

    assert after > before, f"expected rise after STEP; before={before}, after={after}"
