"""Frame-0 voice-derived initialisation for ``_render_clause_full``.

The Klatt frame-stream parity audit (``docs/frame-parity-audit-issue86.md``,
issue #148) identified that the very first emitted frame's
``parstochip[OUT_F1 / OUT_B1 / OUT_TLT / OUT_T0]`` carried PARAMETER-struct
defaults (``B1=0``, ``TLT=5``, ``T0=500``) rather than voice-derived
values: the C-side speaker-tuning chain in ``ph_vset.c`` (lines 607-630)
loads ``f0_dep_tilt`` / ``spdefb1off`` from ``curspdef[]`` before the
per-frame loop runs, but the Python pipeline left those at zero and so
``_compute_tilt`` fell through to its zero-input branch (TLT=5 clamp)
and ``frac4mul(parstochip[OUT_B1], 0)`` zeroed B1 every frame.

The fix in :func:`dectalk.api.speak._render_clause_full` seeds:

- ``f0_dep_tilt = 73`` (Paul's ``paul_8.FT`` from ``p_us_vdf1.c`` line 150),
- ``spdefb1off = 4096`` (Paul's ``paul_8.BR = 0`` → ``(0*0)>>1 + 4096``
  per ``ph_vset.c`` line 629),
- ``f0 = f0minimum`` (so the first ``pht0draw`` frame's ``f0prime`` lives
  above the LOWEST_F0 = 500 deciHz safety clamp).

These assertions lock in the voice-derived first frame so future changes
to the per-frame driver can't silently regress.

Note: after issue #139 dropped the spurious leading ``GEN_SIL`` prepend
in ``us_phalloph2``, frame 0 now captures the smoother's initial state
(F1 ~ 142 Hz) before ``phsettar`` has loaded the first allophone's
target. The B1 / TLT / T0 frame-0 asserts below remain meaningful
because those values flow from the voice-tuning seeds (which run before
the per-frame loop) rather than from the allophone-target chain. The F1
assertion shifted to an early-but-not-first frame (5) where the smoother
has already begun tugging F1 toward the HX target.
"""

from __future__ import annotations

import numpy as np
import pytest

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.param_indices import OUT_B1, OUT_F1, OUT_T0, OUT_TLT
from dectalk.ph.spdef_chip import SpdChip


def _capture_frames(text: str, monkeypatch: pytest.MonkeyPatch) -> list[list[int]]:
    """Run ``_render_clause_full`` and return all emitted ``parstochip`` snapshots."""
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    import dectalk.ph.parstochip_to_frames as ptf  # noqa: PLC0415
    from dectalk.api.speak import _render_clause_full  # noqa: PLC0415

    snapshots: list[list[int]] = []
    real = ptf.parstochip_to_llframe_delayed

    def _capture(
        parstochip: list[int],
        previous: list[int] | None,
        spd_chip: SpdChip | None = None,
    ) -> LLFrame:
        snapshots.append(list(parstochip))
        return real(parstochip, previous, spd_chip)

    monkeypatch.setattr(ptf, "parstochip_to_llframe_delayed", _capture)
    import dectalk.api.speak as speak_mod  # noqa: PLC0415

    if hasattr(speak_mod, "parstochip_to_llframe_delayed"):
        monkeypatch.setattr(speak_mod, "parstochip_to_llframe_delayed", _capture)

    samples = _render_clause_full(
        text,
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert isinstance(samples, np.ndarray)
    assert samples.size > 0, f"{text!r} produced no audio"
    assert snapshots, f"{text!r} emitted no frames"
    return snapshots


def _capture_frame0(text: str, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Run ``_render_clause_full`` and return the first emitted ``parstochip``."""
    return _capture_frames(text, monkeypatch)[0]


def test_frame0_b1_is_voice_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frame 0 ``parstochip[OUT_B1]`` is not the calloc'd-zero default.

    Per the frame-parity audit's root-cause #1, the pre-fix Python
    pipeline always emitted ``B1=0`` on frame 0 because
    ``spdefb1off`` was zero, so ``frac4mul(B1, 0) = 0`` in
    ``ph_draw.c`` line 417. With ``spdefb1off = 4096`` (Q12 unity)
    the value should now reflect the first allophone's speaker-table
    target (HX → ~400 Hz).
    """
    frame0 = _capture_frame0("hello world", monkeypatch)
    assert frame0[OUT_B1] != 0, (
        f"frame 0 OUT_B1 is still 0 (PARAMETER default) — speaker-tuning "
        f"seed for spdefb1off is missing. Full frame: {frame0[:10]}"
    )
    # Paul's HX target B1 is 400 Hz (`p_us_tar.c` HX row); the per-frame
    # smoothing keeps it within a small band of that. Allow a wide
    # tolerance because the trajectory may shift as PH stages evolve.
    assert 100 <= frame0[OUT_B1] <= 1000, (
        f"frame 0 OUT_B1 = {frame0[OUT_B1]} is out of plausible voice-derived range (100..1000 Hz)"
    )


def test_frame0_tlt_is_voice_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frame 0 ``parstochip[OUT_TLT]`` reflects ``f0_dep_tilt``, not 5.

    Pre-fix the value was 5 — ``temptilt = 8 - frac4mul(f0 - 900, 0) =
    8`` then ``tilt_value = 8 + 0 - 3 = 5`` (the constant fall-through
    when ``f0_dep_tilt = 0``). With ``f0_dep_tilt = 73`` (Paul's SPD_FT)
    and the seeded ``f0 = f0minimum = 880`` the computed value shifts.
    """
    frame0 = _capture_frame0("hello world", monkeypatch)
    # Sanity-bound: the synth-side TLT clamp is [0, 31]. The pre-fix
    # constant fallthrough of 5 is the failure signature.
    assert 0 <= frame0[OUT_TLT] <= 31, (
        f"frame 0 OUT_TLT = {frame0[OUT_TLT]} outside legal [0, 31] range"
    )
    # The exact value depends on the seeded f0 — test that it's not the
    # pre-fix constant default. With our seeds it lands at 6.
    assert frame0[OUT_TLT] != 5, (
        "frame 0 OUT_TLT = 5 — speaker-tuning seed for f0_dep_tilt is "
        "missing (the value reverts to the 8-0-3 constant fallthrough)"
    )


def test_frame0_t0_is_above_safety_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frame 0 ``parstochip[OUT_T0]`` is not the LOWEST_F0 = 500 clamp.

    Pre-fix Python emitted T0=500 because ``f0 = 0`` initially and
    ``f0prime = f0 + f0s ≈ 0`` then scaled to below LOWEST_F0 = 500
    deciHz, hitting the safety clamp. Seeding ``f0 = f0minimum`` (Paul:
    880 deciHz = 88 Hz) lifts frame 0 above the clamp.
    """
    frame0 = _capture_frame0("hello world", monkeypatch)
    assert frame0[OUT_T0] > 500, (
        f"frame 0 OUT_T0 = {frame0[OUT_T0]} is at or below the LOWEST_F0 "
        "safety clamp (500 deciHz) — f0 seed for hard-init is missing"
    )
    # Sanity-bound: HIGHEST_F0 = 5121 deciHz = 512.1 Hz.
    assert frame0[OUT_T0] <= 5121, f"frame 0 OUT_T0 = {frame0[OUT_T0]} above HIGHEST_F0 clamp"


def test_early_f1_is_voice_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    """An early frame's ``parstochip[OUT_F1]`` reflects the first allophone's target.

    For ``hello world`` the first allophone is HX (whose F1 target is
    around 730 Hz per the C oracle and ``p_us_tar.c``). The per-frame
    smoothing tugs the emitted F1 toward HX's ``tarcur`` rather than
    leaving it at any PARAMETER-struct default.

    Note: post-issue #139 (leading GEN_SIL prepend removed in
    ``us_phalloph2``), frame 0 captures the smoother's *initial state*
    (F1 ~ 142 Hz) before ``phsettar`` has loaded HX's target. Pre-#139
    the leading GEN_SIL gave the smoother ~15 SIL frames to settle, so
    frame 0 already reflected HX. Now we look at frame 5 — by then the
    target has been loaded and the smoother has begun tugging F1
    upward toward HX (~459 Hz for ``hello world``).
    """
    frames = _capture_frames("hello world", monkeypatch)
    # We need at least a handful of frames to observe the smoothing
    # ramp. ``hello world`` produces ~217 frames, so any reasonable
    # smoke run will have many more than 6.
    assert len(frames) >= 6, f"expected >= 6 frames, got {len(frames)}"
    frame5 = frames[5]
    # F1 floor from `parstochip_to_frames._clamp` is 100; an unset
    # PARAMETER default would have left it near the bottom of the
    # range (audit refresh recorded 459 for `hi` and 596 for
    # `hello world`). The post-fix value should still sit in the
    # 100..1300 Hz physical range.
    assert 100 <= frame5[OUT_F1] <= 1300, (
        f"frame 5 OUT_F1 = {frame5[OUT_F1]} outside legal [100, 1300] Hz range"
    )
    # The first allophone is HX; its F1 target is ~730 Hz and the
    # per-frame smoothing pulls F1 from the initial state (~142 Hz)
    # toward that target. By frame 5 the value should clearly be on
    # its way up. A value below ~300 would indicate the PH driver
    # isn't running ``phsettar`` for nphone=0 before the first emit.
    assert frame5[OUT_F1] >= 300, (
        f"frame 5 OUT_F1 = {frame5[OUT_F1]} is suspiciously low — first "
        "allophone's F1 target (~730 Hz for HX) does not appear to have "
        "been loaded"
    )
    # Sanity-check the trajectory: frame 5 should be strictly higher
    # than frame 0 (F1 ramping toward HX target). If they're equal the
    # smoother isn't being driven.
    assert frame5[OUT_F1] > frames[0][OUT_F1], (
        f"F1 not increasing across early frames: frame 0 = {frames[0][OUT_F1]}, "
        f"frame 5 = {frame5[OUT_F1]}"
    )
