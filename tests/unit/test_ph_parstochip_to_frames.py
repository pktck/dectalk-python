"""Tests for :mod:`dectalk.ph.parstochip_to_frames`."""

from __future__ import annotations

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_T0,
    OUT_TLT,
)
from dectalk.ph.parstochip_to_frames import (
    parstochip_to_llframe,
    parstochip_to_llframe_delayed,
)


def _empty_parstochip() -> list[int]:
    """64-cell parstochip buffer (the size phdraw uses)."""
    return [0] * 64


def test_default_input_produces_safe_frame() -> None:
    """All-zero parstochip should yield a silent frame with a sane F0 fallback."""
    frame = parstochip_to_llframe(_empty_parstochip())
    assert isinstance(frame, LLFrame)
    assert frame.AV == 0
    # F0 must be non-zero so the synthesizer source has a period to lock to;
    # OUT_T0=0 means pht0draw hasn't run yet.
    assert frame.F0 == 1220  # 122 Hz fallback (deciHz).


def test_pop_through_basic_cells() -> None:
    """Populated parstochip cells flow to the matching LLFrame fields."""
    p = _empty_parstochip()
    p[OUT_T0] = 1500
    p[OUT_AV] = 60
    p[OUT_AP] = 25
    p[OUT_F1] = 500
    p[OUT_B1] = 80
    p[OUT_F2] = 1500
    p[OUT_F3] = 2500
    p[OUT_FZ] = 280
    p[OUT_TLT] = 8
    p[OUT_A2] = 40
    frame = parstochip_to_llframe(p)
    assert frame.F0 == 1500
    assert frame.AV == 60
    assert frame.Ah == 25
    assert frame.F1 == 500
    assert frame.B1 == 80
    assert frame.F2 == 1500
    assert frame.F3 == 2500
    assert frame.FNZ == 280
    # OUT_TLT goes through the lineartilt[] remap (ph_romi.c lines 96-103):
    # lineartilt[8] == 23.
    assert frame.TL == 23
    assert frame.A2f == 40


def test_amplitude_clamped_to_80db() -> None:
    """Out-of-range parstochip values are clamped instead of overflowing."""
    p = _empty_parstochip()
    p[OUT_AV] = 1000
    p[OUT_AP] = 500
    p[OUT_A2] = -50
    frame = parstochip_to_llframe(p)
    assert frame.AV == 80
    assert frame.Ah == 80
    assert frame.A2f == 0


def test_formant_clamped_to_safe_synthesizer_range() -> None:
    """Formant frequencies clamp so the synth filter coefficients stay stable."""
    p = _empty_parstochip()
    p[OUT_F1] = 100000
    p[OUT_F2] = -42
    frame = parstochip_to_llframe(p)
    assert 100 <= frame.F1 <= 1300
    assert 500 <= frame.F2 <= 3000


def test_higher_formants_get_synth_neutral_defaults() -> None:
    """F4..F6 and B4..B6 fall back to LLFrame's neutral resting values."""
    frame = parstochip_to_llframe(_empty_parstochip())
    assert frame.F4 == 3500
    assert frame.B4 == 250
    assert frame.F5 == 4500
    assert frame.F6 == 5500


# -- Delayed adapter (ph_claus.c send_pars one-frame delay) -----------------


def test_delayed_first_call_falls_back_to_current() -> None:
    """With ``previous_parstochip=None`` the first emit mirrors the current frame.

    The C source's first call to ``send_pars()`` seeds ``delaypars[]`` with
    AV=TLT=T0=0 and writes the current frame's F1/B1/etc into delaypars
    *without* spcwrite'ing yet; the Python port collapses that to emit one
    frame populated from the current parstochip when the previous is None.
    """
    p = _empty_parstochip()
    p[OUT_F1] = 500
    p[OUT_AV] = 60
    frame = parstochip_to_llframe_delayed(p, None)
    assert frame.F1 == 500
    assert frame.AV == 60


def test_delayed_uses_previous_for_formant_slots() -> None:
    """Second-frame emit takes F1/B1/etc from previous, AV/TL/T0 from current."""
    prev = _empty_parstochip()
    prev[OUT_F1] = 500
    prev[OUT_F2] = 1500
    prev[OUT_AV] = 99  # should NOT appear in the output frame.
    cur = _empty_parstochip()
    cur[OUT_F1] = 700  # should NOT appear (delayed slot).
    cur[OUT_F2] = 1800  # should NOT appear.
    cur[OUT_AV] = 60  # should appear (real-time slot).
    cur[OUT_T0] = 1500  # should appear (real-time slot).
    frame = parstochip_to_llframe_delayed(cur, prev)
    # Delayed slots come from prev:
    assert frame.F1 == 500
    assert frame.F2 == 1500
    # Real-time slots come from cur:
    assert frame.AV == 60
    assert frame.F0 == 1500


def test_delayed_applies_lineartilt_to_current_tlt() -> None:
    """``parstochip[OUT_TLT]`` is run through ``lineartilt`` for the LLFrame ``TL``."""
    cur = _empty_parstochip()
    cur[OUT_TLT] = 5
    frame = parstochip_to_llframe_delayed(cur, _empty_parstochip())
    # lineartilt[5] == 17 (ph_romi.c lines 96-103).
    assert frame.TL == 17
