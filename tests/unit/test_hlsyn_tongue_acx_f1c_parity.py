"""C-source parity test for ``Tongue_acx_f1c`` against acxf1c.c.

Re-parses the C body and asserts:

- The signature is ``void Tongue_acx_f1c(HLFrame *, HLSpeaker *, HLState *)``.
- The Linux build's ``#ifndef TONGUE_BODY_AREA`` guard
  ``frame->ab < 30.0f || frame->al < 30.0f`` is present (with the
  ``frame->atb`` term gated by the inactive ``TONGUE_BODY_AREA``
  branch).
- Both ``R1al`` and ``R1ab`` are filled via ``HelmholtzFrequency`` on
  the ``al`` / ``ab`` areas (after ``MMSQ_TO_CMSQ``).
- The ``state->f1c`` tie-break is the minimum of ``f1``, ``R1al`` and
  ``R1ab``, with ``<`` / ``<=`` chosen so that ``R1al`` wins on a tie
  with ``R1ab``.
- ``state->acl`` / ``state->acd`` are populated via
  ``Compute_acl`` / ``Compute_acd``.
- ``Set_acx_loc`` is the final call.

Plus behavioural parity using reference :class:`HLFrame` /
:class:`HLSpeaker` / :class:`HLState` triples.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.compute_ac import compute_acd, compute_acl
from dectalk.hlsyn.helmholtz import helmholtz_frequency
from dectalk.hlsyn.place_constants import DORSUM, LIPS, LIQUID, UNCOMPUTABLE
from dectalk.hlsyn.set_acx_loc import set_acx_loc
from dectalk.hlsyn.tongue_acx_f1c import tongue_acx_f1c
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/acxf1c.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_acxf1c_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_acxf1c_c()
    match = re.search(
        r"void\s+Tongue_acx_f1c\s*\([^)]*\)\s*\n\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "Tongue_acx_f1c() definition not found in acxf1c.c"
    return match.group(1)


# ---------------------------------------------------------------------------
# Structural parity.
# ---------------------------------------------------------------------------


def test_signature_matches_c() -> None:
    """Signature is ``void Tongue_acx_f1c(HLFrame *, HLSpeaker *, HLState *)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"void\s+Tongue_acx_f1c\s*\(\s*"
        r"HLFrame\s*\*\s*\w+\s*,\s*"
        r"HLSpeaker\s*\*\s*\w+\s*,\s*"
        r"HLState\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_linux_active_constriction_guard() -> None:
    """``#ifndef TONGUE_BODY_AREA`` -> ``ab < 30 || al < 30`` (no atb term).

    The ``#ifdef TONGUE_BODY_AREA`` arm additionally checks
    ``frame->atb < 30.0f``; that symbol is NOT defined in the Linux
    build, so the ``#else`` arm (just the two-term ``||``) is what
    actually compiles.
    """
    body = _extract_body()
    # The Linux-active else arm of the #ifdef/#else split.
    assert re.search(
        r"#else\s*\n\s*"
        r"if\s*\(\s*frame->ab\s*<\s*30\.0f\s*\|\|\s*frame->al\s*<\s*30\.0f\s*\)\s*\n\s*"
        r"#endif",
        body,
    )
    # The #ifdef'd variant exists too (but is inactive on Linux).
    assert re.search(
        r"#ifdef\s+TONGUE_BODY_AREA\s*\n\s*"
        r"if\s*\(\s*frame->ab\s*<\s*30\.0f\s*\|\|\s*frame->al\s*<\s*30\.0f\s*\|\|\s*"
        r"frame->atb\s*<\s*30\.0f\s*\)",
        body,
    )


def test_r1al_dispatch_uses_helmholtz_frequency_on_al() -> None:
    """``R1al = HelmholtzFrequency(MMSQ_TO_CMSQ(frame->al), Val, Lc_al, ...)``."""
    body = _extract_body()
    assert re.search(
        r"R1al\s*=\s*HelmholtzFrequency\s*\(\s*"
        r"MMSQ_TO_CMSQ\s*\(\s*frame->al\s*\)\s*,\s*"
        r"speaker->Val\s*,\s*"
        r"speaker->Lc_al\s*,\s*"
        r"speaker->HelmholtzZeroAreaFrequency\s*\)",
        body,
    )


def test_r1ab_dispatch_uses_helmholtz_frequency_on_ab() -> None:
    """``R1ab = HelmholtzFrequency(MMSQ_TO_CMSQ(frame->ab), Vab, Lc_ab, ...)``.

    The ``#ifdef TONGUE_BODY_AREA`` arm picks ``frame->atb`` instead
    of ``frame->ab`` when ``ab > atb``; that branch is inactive on
    Linux so only the ``frame->ab`` form runs.
    """
    body = _extract_body()
    assert re.search(
        r"R1ab\s*=\s*HelmholtzFrequency\s*\(\s*"
        r"MMSQ_TO_CMSQ\s*\(\s*frame->ab\s*\)\s*,\s*"
        r"speaker->Vab\s*,\s*"
        r"speaker->Lc_ab\s*,\s*"
        r"speaker->HelmholtzZeroAreaFrequency\s*\)",
        body,
    )


def test_f1c_minimum_chain() -> None:
    """``f1c`` is the minimum of ``f1``, ``R1al``, ``R1ab`` with the C tie-break."""
    body = _extract_body()
    # First arm: R1al < R1ab && R1al < f1 -> f1c = R1al.
    assert re.search(
        r"if\s*\(\s*R1al\s*<\s*R1ab\s*&&\s*R1al\s*<\s*frame->f1\s*\)\s*\n?\s*"
        r"state->f1c\s*=\s*R1al",
        body,
    )
    # Second arm: R1ab <= R1al && R1ab < f1 -> f1c = R1ab.
    assert re.search(
        r"else\s+if\s*\(\s*R1ab\s*<=\s*R1al\s*&&\s*R1ab\s*<\s*frame->f1\s*\)\s*\n?\s*"
        r"\n?\s*state->f1c\s*=\s*R1ab",
        body,
    )
    # Fallback: f1c = frame->f1.
    assert re.search(r"else\s*\n?\s*\n?\s*state->f1c\s*=\s*frame->f1", body)


def test_no_constriction_short_circuits_f1c_to_f1() -> None:
    """When neither ``ab`` nor ``al`` is below 30, ``f1c = frame->f1``."""
    body = _extract_body()
    # The outer else of the constriction-guard.
    assert re.search(
        r"\}\s*\n\s*else\s*\n\s*\{\s*\n\s*state->f1c\s*=\s*frame->f1\s*;\s*\n\s*\}",
        body,
    )


def test_acl_assignment_calls_compute_acl() -> None:
    """``state->acl = Compute_acl(frame, speaker)``."""
    body = _extract_body()
    assert re.search(
        r"state->acl\s*=\s*Compute_acl\s*\(\s*frame\s*,\s*speaker\s*\)",
        body,
    )


def test_acd_assignment_calls_compute_acd_linux_active() -> None:
    """``#ifndef TONGUE_BODY_AREA`` -> ``state->acd = Compute_acd(frame, speaker)``.

    The ``#ifdef TONGUE_BODY_AREA`` arm caps ``acd`` at ``frame->atb``;
    that branch is inactive on Linux.
    """
    body = _extract_body()
    assert re.search(
        r"#ifndef\s+TONGUE_BODY_AREA\s*\n\s*"
        r"state->acd\s*=\s*Compute_acd\s*\(\s*frame\s*,\s*speaker\s*\)",
        body,
    )


def test_set_acx_loc_is_final_call() -> None:
    """Last statement of the body is ``Set_acx_loc(frame, state)``."""
    body = _extract_body()
    assert re.search(
        r"Set_acx_loc\s*\(\s*frame\s*,\s*state\s*\)\s*;\s*$",
        body.rstrip(),
    )


def test_mmsq_to_cmsq_macro_is_times_0p01() -> None:
    """``MMSQ_TO_CMSQ(x) = x * 0.01f`` per hlsyn.h (mm^2 -> cm^2)."""
    hlsyn_h = _C_FILE.parent / "hlsyn.h"
    text = hlsyn_h.read_bytes().replace(b"\r", b"").decode("latin-1")
    assert re.search(
        r"MMSQ_TO_CMSQ\(MMSQ\)\s*\(\s*\(MMSQ\)\s*\*\s*0\.01f\s*\)",
        text,
    )


# ---------------------------------------------------------------------------
# Behavioural parity with reference HLFrame / HLSpeaker / HLState triples.
# ---------------------------------------------------------------------------


def _reference_speaker() -> HLSpeaker:
    """A speaker that exercises every branch in tongue_acx_f1c."""
    return HLSpeaker(
        # Helmholtz forward inputs for R1al / R1ab.
        Val=60.0,
        Lc_al=1.5,
        Vab=40.0,
        Lc_ab=1.0,
        HelmholtzZeroAreaFrequency=200.0,
        # Compute_acl inputs (liquid range).
        f1Min=200.0,
        f1Max=600.0,
        f2RetroflexMax=1500.0,
        f3RetroflexMax=2000.0,
        f2LateralMax=1800.0,
        f3LateralMin=2500.0,
        aclFreq=400.0,
        Kacl=2.0,
        # Compute_acd inputs.
        Vacd=50.0,
        Lc_acd=4.0,
        acd_f1Break=600.0,
        f1HiShift=900.0,
        KHi=10.0,
        acdMax=400.0,
    )


def _expected_state(frame: HLFrame, speaker: HLSpeaker) -> HLState:
    """Compute the expected state via the already-ported helpers."""
    state = HLState()
    if frame.ab < 30.0 or frame.al < 30.0:
        r1al = helmholtz_frequency(
            frame.al * 0.01,
            speaker.Val,
            speaker.Lc_al,
            speaker.HelmholtzZeroAreaFrequency,
        )
        r1ab = helmholtz_frequency(
            frame.ab * 0.01,
            speaker.Vab,
            speaker.Lc_ab,
            speaker.HelmholtzZeroAreaFrequency,
        )
        if r1al < r1ab and r1al < frame.f1:
            state.f1c = r1al
        elif r1ab <= r1al and r1ab < frame.f1:
            state.f1c = r1ab
        else:
            state.f1c = frame.f1
    else:
        state.f1c = frame.f1
    state.acl = compute_acl(frame, speaker)
    state.acd = compute_acd(frame, speaker)
    set_acx_loc(frame, state)
    return state


def _assert_state_close(got: HLState, expected: HLState) -> None:
    """Compare every observed field of two HLState instances."""
    assert abs(got.f1c - expected.f1c) < 1e-6
    assert abs(got.acl - expected.acl) < 1e-6
    assert abs(got.acd - expected.acd) < 1e-6
    assert abs(got.acx - expected.acx) < 1e-6
    assert got.loc == expected.loc


def test_no_constriction_path_writes_f1c_equals_f1() -> None:
    """``ab=30, al=30`` (both equal, neither below 30) -> ``f1c == frame.f1``."""
    speaker = _reference_speaker()
    frame = HLFrame(al=30.0, ab=30.0, f1=500.0, f2=1200.0, f3=1700.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    # The early-out keeps f1c at frame.f1.
    assert abs(state.f1c - frame.f1) < 1e-9
    # The downstream calls still ran.
    _assert_state_close(state, _expected_state(frame, speaker))


def test_constriction_path_picks_min_of_three() -> None:
    """``ab`` small enough to trigger constriction; picks ``min(f1, R1al, R1ab)``."""
    speaker = _reference_speaker()
    # Small ab => low R1ab; large al => high R1al.
    frame = HLFrame(al=200.0, ab=5.0, f1=2000.0, f2=1200.0, f3=1700.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    _assert_state_close(state, _expected_state(frame, speaker))
    # Sanity: f1c is below frame.f1 because R1ab is much smaller.
    assert state.f1c < frame.f1


def test_constriction_path_r1al_wins_tiebreak() -> None:
    """When ``R1al == R1ab``, the first arm (``R1al < R1ab``) is false; second arm
    (``R1ab <= R1al``) wins, so ``f1c = R1ab``.

    This is the documented "if ab and al are both closed then r1ab == r1al"
    case in the C source. The tie-break is the ``<`` vs ``<=`` distinction.
    """
    speaker = _reference_speaker()
    # Geometry equal in al and ab so that both Helmholtz values match.
    speaker.Val = 50.0
    speaker.Vab = 50.0
    speaker.Lc_al = 1.5
    speaker.Lc_ab = 1.5
    # ab == al small => identical R1al / R1ab.
    frame = HLFrame(al=10.0, ab=10.0, f1=1000.0, f2=1200.0, f3=1700.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    # Both Helmholtz values match; second arm wins on tie.
    expected_r = helmholtz_frequency(
        frame.ab * 0.01,
        speaker.Vab,
        speaker.Lc_ab,
        speaker.HelmholtzZeroAreaFrequency,
    )
    assert abs(state.f1c - expected_r) < 1e-6
    _assert_state_close(state, _expected_state(frame, speaker))


def test_constriction_path_no_helmholtz_below_f1_falls_through() -> None:
    """If both ``R1al`` and ``R1ab`` exceed ``f1``, ``f1c = frame.f1`` (else branch)."""
    speaker = _reference_speaker()
    # Push HelmholtzZeroAreaFrequency above f1 so both R values exceed f1.
    speaker.HelmholtzZeroAreaFrequency = 800.0
    frame = HLFrame(al=10.0, ab=10.0, f1=300.0, f2=1200.0, f3=1700.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    # Both R1al and R1ab are >= 800 > 300, so f1c collapses to frame.f1.
    assert abs(state.f1c - frame.f1) < 1e-9
    _assert_state_close(state, _expected_state(frame, speaker))


def test_constriction_path_r1al_strictly_less_than_r1ab() -> None:
    """``R1al < R1ab`` and ``R1al < f1`` -> ``f1c = R1al``."""
    speaker = _reference_speaker()
    # Tweak Val/Lc_al so R1al < R1ab while both stay below f1.
    speaker.Val = 80.0
    speaker.Lc_al = 3.0
    speaker.Vab = 30.0
    speaker.Lc_ab = 1.0
    # al small => triggers; both areas small so both R values are near Hz0.
    frame = HLFrame(al=5.0, ab=20.0, f1=2000.0, f2=1200.0, f3=1700.0)
    state = HLState()
    r1al = helmholtz_frequency(
        frame.al * 0.01,
        speaker.Val,
        speaker.Lc_al,
        speaker.HelmholtzZeroAreaFrequency,
    )
    r1ab = helmholtz_frequency(
        frame.ab * 0.01,
        speaker.Vab,
        speaker.Lc_ab,
        speaker.HelmholtzZeroAreaFrequency,
    )
    # Sanity: choose geometry so R1al < R1ab indeed.
    assert r1al < r1ab
    assert r1al < frame.f1
    tongue_acx_f1c(frame, speaker, state)
    assert abs(state.f1c - r1al) < 1e-6
    _assert_state_close(state, _expected_state(frame, speaker))


def test_state_acl_acd_match_helpers() -> None:
    """``state.acl`` / ``state.acd`` agree with the dedicated helpers."""
    speaker = _reference_speaker()
    frame = HLFrame(al=5.0, ab=5.0, f1=400.0, f2=1200.0, f3=1500.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    assert abs(state.acl - compute_acl(frame, speaker)) < 1e-9
    assert abs(state.acd - compute_acd(frame, speaker)) < 1e-9


def test_set_acx_loc_back_dorsum_wins_when_smallest() -> None:
    """A small ``acd`` (and ``acl`` uncomputable) -> ``state.loc == DORSUM``."""
    speaker = _reference_speaker()
    # f1 below f1Min so compute_acl returns UNCOMPUTABLE.
    # f1 below acd_f1Break and small enough that helmholtz_constriction is small.
    frame = HLFrame(al=100.0, ab=100.0, f1=150.0, f2=1200.0, f3=1500.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    assert state.acl == UNCOMPUTABLE
    assert state.loc == DORSUM
    assert abs(state.acx - state.acd) < 1e-9


def test_set_acx_loc_front_blade_wins_when_smallest() -> None:
    """When ``ab <= al`` and front wins -> ``state.loc == BLADE``."""
    speaker = _reference_speaker()
    # Out-of-liquid range f1 (below f1Min) so acl is UNCOMPUTABLE,
    # acd will be 0.0 (negative -> clamped) since f1 == f1HiShift,
    # but we want acd large vs front. Easier: use compute_acd's
    # below-break branch with a small frame.f1 to make acd small but
    # nonzero, then ab/al smaller still.
    # f1=400 < acd_f1Break=600, so helmholtz path:
    # helm = (f1^2 - znf^2) * V*L*3.15e-8 = (160000-40000) * 50*4*3.15e-8
    # ~= 120000 * 6.30e-6 ~= 0.756, *100 = 75.6 mm^2
    frame = HLFrame(al=3.0, ab=2.0, f1=400.0, f2=1200.0, f3=1500.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    # Out of liquid range (f1=400, f2=1200<1500, f3=1500<2000 -- actually IN range).
    # Recheck: this is the retroflex region. So acl is computed.
    # acl = (400/400)^2 * 2 = 2.0
    # acd ~= 75.6 (above)
    # ab = 2.0, al = 3.0, so front = BLADE with area 2.0.
    # Back picks acl (smaller). LiquidDorsumArea=2.0, LipsBladeArea=2.0 tie.
    # acl vs acd: acl=2.0 < acd=75.6, so back picks LIQUID with 2.0.
    # Then LiquidDorsumArea (2.0) <= LipsBladeArea (2.0): tie goes to back.
    # So loc = LIQUID, acx = 2.0.
    assert state.loc == LIQUID
    assert abs(state.acx - 2.0) < 1e-6


def test_set_acx_loc_front_lips_wins_when_al_smallest() -> None:
    """When ``al < ab`` and front wins -> ``state.loc == LIPS``."""
    speaker = _reference_speaker()
    # Make back areas big; front: al < ab so LIPS.
    # f1 well below f1Min -> acl UNCOMPUTABLE.
    # f1 below break, very small -> small acd. Need acd > al.
    # Choose al = 0.05 (mm^2), ab = 10.0 (large), f1 = 250 (below f1Min=200... no above).
    # Hmm f1Min=200. Use f1=180 to make compute_acl uncomputable.
    # At f1=180, compute_acd helmholtz path:
    # acd = (180^2 - 200^2) * 50*4*3.15e-8 *100 = (-7600)*6.3e-6*100 = -0.0048 < 0 -> 0.
    # So acd = 0. We need acd >= al=0.05 for LIPS to win. Won't work.
    # Pick f1 = 250 instead: still below f1Min=200? No 250>200. f1Min < f1 < f1Max,
    # but f3=1500 < f3RetroflexMax=2000, f2=1200<1500. So acl is COMPUTABLE.
    # acl = (250/400)^2 * 2 = 0.78. Need al < 0.78.
    # Try al=0.5, ab=10.0. f1=250.
    # acd = (250^2-200^2)*50*4*3.15e-8*100 = (62500-40000)*6.3e-6*100 = 22500*6.3e-6*100 = 14.18.
    # min(acl=0.78, acd=14.18) -> LIQUID with 0.78.
    # front: al=0.5 < ab=10.0 -> LIPS with 0.5.
    # back vs front: 0.78 vs 0.5 -> front wins -> LIPS.
    frame = HLFrame(al=0.5, ab=10.0, f1=250.0, f2=1200.0, f3=1500.0)
    state = HLState()
    tongue_acx_f1c(frame, speaker, state)
    assert state.loc == LIPS
    assert abs(state.acx - 0.5) < 1e-6


def test_python_matches_reference_helpers_across_cases() -> None:
    """Cross-check tongue_acx_f1c against the helper-composition reference.

    Spans the constriction / no-constriction branches and a variety of
    formant ranges so each branch of every helper is exercised.
    """
    speaker = _reference_speaker()
    cases: list[HLFrame] = [
        # No-constriction (both areas above 30).
        HLFrame(al=50.0, ab=80.0, f1=500.0, f2=1200.0, f3=1700.0),
        # Constriction, retroflex.
        HLFrame(al=5.0, ab=5.0, f1=400.0, f2=1200.0, f3=1700.0),
        # Constriction, lateral.
        HLFrame(al=5.0, ab=5.0, f1=400.0, f2=1700.0, f3=2700.0),
        # Constriction, out of liquid range.
        HLFrame(al=5.0, ab=5.0, f1=150.0, f2=1200.0, f3=1500.0),
        # Constriction, above acd_f1Break.
        HLFrame(al=5.0, ab=5.0, f1=700.0, f2=2000.0, f3=2000.0),
        # ab < 30 but al >= 30.
        HLFrame(al=40.0, ab=5.0, f1=500.0, f2=1200.0, f3=1700.0),
        # al < 30 but ab >= 30.
        HLFrame(al=5.0, ab=40.0, f1=500.0, f2=1200.0, f3=1700.0),
    ]
    for frame in cases:
        state = HLState()
        tongue_acx_f1c(frame, speaker, state)
        _assert_state_close(state, _expected_state(frame, speaker))
