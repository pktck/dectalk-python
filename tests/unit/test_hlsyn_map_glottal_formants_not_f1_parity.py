"""C-source parity test for ``MapGlottalFormantsNotF1``.

Re-parses ``src/dapi/src/hlsyn/hlframe.c`` -- specifically the
``MapGlottalFormantsNotF1`` static helper near line 181 -- and asserts:

- The signature is
  ``static void MapGlottalFormantsNotF1(HLFrame *, HLSpeaker *, HLState *, LLFrame *)``.
- The Linux-active body writes ``llframe->NF0`` from
  ``frame->f0 + 0.5f`` (with the ``#ifdef in_phdraw`` correction terms
  gated by an inactive symbol).
- The tracheal-coupling guard is ``frame->an < 3.0f && state->f1c < 185.0f``
  AND ``state->agf > speaker->agm && state->f1c < speaker->F1T``.
- The f1c bump is
  ``state->f1c += speaker->KdF * (1 - state->f1c/speaker->F1T) * (state->agf - speaker->agm)``.
- ``llframe->NF2/NF3/NF4/NF5`` are assigned from
  ``(short)frame->f2/.f3/.f4/speaker->F5``.

Plus behavioural parity covering every branch of the f1c-bump
conditional and every NF* assignment.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.hlsyn.map_glottal_formants_not_f1 import map_glottal_formants_not_f1
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn"
_HLFRAME_C = _C_DIR / "hlframe.c"

pytestmark = pytest.mark.skipif(
    not _HLFRAME_C.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``MapGlottalFormantsNotF1`` (raw, comments kept)."""
    text = _read(_HLFRAME_C)
    # Match the *definition*, not the prototype (prototype lacks a body).
    # The definition lives at line 180-224 and starts on its own line.
    match = re.search(
        r"static\s+void\s*\n\s*MapGlottalFormantsNotF1\s*\([^)]*\)\s*\n\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "MapGlottalFormantsNotF1() definition not found in hlframe.c"
    return match.group(1)


# ---------------------------------------------------------------------------
# Structural parity.
# ---------------------------------------------------------------------------


def test_signature_matches_c() -> None:
    """``static void MapGlottalFormantsNotF1(HLFrame *, HLSpeaker *, HLState *, LLFrame *)``."""
    text = _read(_HLFRAME_C)
    # The definition (not the prototype) has a newline between ``void`` and
    # the name; the prototype keeps them on one line.
    sig = re.search(
        r"static\s+void\s*\n\s*MapGlottalFormantsNotF1\s*\(\s*"
        r"HLFrame\s*\*\s*\w+\s*,\s*"
        r"HLSpeaker\s*\*\s*\w+\s*,\s*"
        r"HLState\s*\*\s*\w+\s*,\s*"
        r"LLFrame\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_nf0_assigned_from_f0_plus_half() -> None:
    """``llframe->NF0 = (short)(frame->f0 + 0.5f)`` in the f0 > 0 branch."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*frame->f0\s*>\s*0\.0f\s*\)\s*\{\s*\n\s*"
        r"llframe->NF0\s*=\s*\(\s*short\s*\)\s*\(\s*\n?\s*"
        r"frame->f0\s*\+\s*0\.5f",
        body,
    )


def test_nf0_clamped_at_zero_in_positive_branch() -> None:
    """Inside the ``f0 > 0`` branch the result is clamped: ``if NF0 < 0 NF0 = 0``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*llframe->NF0\s*<\s*0\s*\)\s*[^\n]*\n?\s*llframe->NF0\s*=\s*0",
        body,
    )


def test_nf0_else_branch_zero() -> None:
    """The ``frame->f0 <= 0`` else-branch writes ``llframe->NF0 = 0``."""
    body = _extract_body()
    assert re.search(r"else\s*\n\s*llframe->NF0\s*=\s*0\s*;", body)


def test_in_phdraw_correction_block_is_ifdef_guarded() -> None:
    """The vowel-shift / Kpd / Kdf0dc corrections are inside ``#ifdef in_phdraw``.

    ``in_phdraw`` is NOT defined in the Linux build, so these
    corrections do not affect the byte-exact path through the C
    oracle.
    """
    body = _extract_body()
    assert re.search(r"#ifdef\s+in_phdraw", body)
    # The vowel-height correction uses Kf1 / f0_vowelshift_f1_break.
    assert re.search(r"speaker->Kf1\s*\*\s*frame->f0", body)
    assert re.search(r"speaker->f0_vowelshift_f1_break", body)
    # The transglottal-pressure correction uses Kpd / CGS_TO_CMWATER(Pm) / Psm.
    assert re.search(
        r"speaker->Kpd\s*\*\s*\(\s*frame->ps\s*-\s*CGS_TO_CMWATER\(\s*state->Pm\s*\)\s*-\s*speaker->Psm",
        body,
    )
    # The glottal-stiffness correction uses Kdf0dc * frame->dc.
    assert re.search(r"speaker->Kdf0dc\s*\*\s*frame->dc", body)
    # And the #endif closes it.
    assert re.search(r"#endif", body)


def test_outer_tracheal_guard_an_and_f1c() -> None:
    """Outer guard: ``frame->an < 3.0f && state->f1c < 185.0f``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*frame->an\s*<\s*3\.0f\s*&&\s*state->f1c\s*<\s*185\.0f\s*\)",
        body,
    )


def test_inner_tracheal_guard_agf_and_f1c_vs_f1t() -> None:
    """Inner guard: ``state->agf > speaker->agm && state->f1c < speaker->F1T``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*state->agf\s*>\s*speaker->agm\s*&&\s*"
        r"state->f1c\s*<\s*speaker->F1T\s*\)",
        body,
    )


def test_f1c_bump_formula_matches_c() -> None:
    """``state->f1c += KdF * (1 - f1c/F1T) * (agf - agm)``."""
    body = _extract_body()
    assert re.search(
        r"state->f1c\s*\+=\s*speaker->KdF\s*\*\s*"
        r"\(\s*1\.0f\s*-\s*state->f1c\s*/\s*speaker->F1T\s*\)\s*\*\s*"
        r"\(\s*state->agf\s*-\s*speaker->agm\s*\)",
        body,
    )


def test_nf2_nf3_nf4_nf5_assignments() -> None:
    """NF2/NF3/NF4/NF5 are ``(short)`` casts of frame.f2/.f3/.f4 and speaker->F5."""
    body = _extract_body()
    assert re.search(r"llframe->NF2\s*=\s*\(\s*short\s*\)\s*frame->f2", body)
    assert re.search(r"llframe->NF3\s*=\s*\(\s*short\s*\)\s*frame->f3", body)
    assert re.search(r"llframe->NF4\s*=\s*\(\s*short\s*\)\s*frame->f4", body)
    assert re.search(r"llframe->NF5\s*=\s*\(\s*short\s*\)\s*speaker->F5", body)


# ---------------------------------------------------------------------------
# Behavioural parity with hand-computed reference values.
# ---------------------------------------------------------------------------


def _reference_speaker() -> HLSpeaker:
    """A speaker that exercises every branch of map_glottal_formants_not_f1."""
    return HLSpeaker(
        agm=0.5,
        F1T=300.0,
        KdF=0.2,
        F5=3850.0,
    )


def _close(a: float, b: float, eps: float = 1e-6) -> bool:
    """Manual epsilon comparison (avoiding pytest.approx for pyright)."""
    return abs(a - b) < eps


# ---- NF0 path ------------------------------------------------------------


def test_nf0_zero_when_f0_zero() -> None:
    """``frame.f0 == 0`` -> ``NF0 = 0``."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=0.0, an=10.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert llframe.NF0 == 0


def test_nf0_zero_when_f0_negative() -> None:
    """``frame.f0 < 0`` -> ``NF0 = 0`` (defensive)."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=-50.0, an=10.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert llframe.NF0 == 0


def test_nf0_rounds_half_up() -> None:
    """``frame.f0 = 120.5`` -> ``NF0 = 121`` (round, not truncate)."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.5, an=10.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # 120.5 + 0.5 = 121.0 -> (short)121 = 121.
    assert llframe.NF0 == 121


def test_nf0_rounds_value_below_half() -> None:
    """``frame.f0 = 119.4`` -> ``NF0 = 119`` (119.4 + 0.5 = 119.9 -> int truncates)."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=119.4, an=10.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # 119.4 + 0.5 = 119.9 -> int(119.9) = 119.
    assert llframe.NF0 == 119


def test_nf0_passthrough_integer() -> None:
    """``frame.f0 = 250.0`` -> ``NF0 = 250`` (clean integer rounding)."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=250.0, an=10.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # 250.0 + 0.5 = 250.5 -> int(250.5) = 250.
    assert llframe.NF0 == 250


# ---- f1c bump conditional ----------------------------------------------


def test_f1c_unchanged_when_an_too_high() -> None:
    """``frame.an >= 3.0`` -> outer guard fails, f1c unchanged."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.0, an=5.0)  # an >= 3
    state = HLState(f1c=100.0, agf=10.0)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert _close(state.f1c, 100.0)


def test_f1c_unchanged_when_f1c_too_high() -> None:
    """``state.f1c >= 185.0`` -> outer guard fails, f1c unchanged."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.0, an=1.0)
    state = HLState(f1c=200.0, agf=10.0)  # f1c >= 185
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert _close(state.f1c, 200.0)


def test_f1c_unchanged_when_agf_below_agm() -> None:
    """``state.agf <= speaker.agm`` -> inner guard fails, f1c unchanged."""
    speaker = _reference_speaker()  # agm=0.5
    frame = HLFrame(f0=120.0, an=1.0)
    state = HLState(f1c=100.0, agf=0.3)  # agf < agm
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert _close(state.f1c, 100.0)


def test_f1c_unchanged_when_f1c_above_f1t() -> None:
    """``state.f1c >= speaker.F1T`` -> inner guard fails, f1c unchanged."""
    speaker = _reference_speaker()  # F1T=300, but we want f1c < 185 yet >= F1T
    speaker.F1T = 100.0  # f1c=150 > F1T=100
    frame = HLFrame(f0=120.0, an=1.0)
    state = HLState(f1c=150.0, agf=10.0)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert _close(state.f1c, 150.0)


def test_f1c_bumped_when_all_guards_pass() -> None:
    """All four guards pass -> f1c is bumped by the explicit formula."""
    speaker = _reference_speaker()  # agm=0.5, F1T=300, KdF=0.2
    frame = HLFrame(f0=120.0, an=1.0)  # an < 3
    state = HLState(f1c=100.0, agf=2.5)  # f1c < 185, agf > agm, f1c < F1T
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # Expected: 100 + 0.2 * (1 - 100/300) * (2.5 - 0.5)
    #         = 100 + 0.2 * (2/3) * 2 = 100 + 0.2667 = 100.2667
    expected = 100.0 + 0.2 * (1.0 - 100.0 / 300.0) * (2.5 - 0.5)
    assert _close(state.f1c, expected, eps=1e-5)


def test_f1c_bump_proportional_to_kdf() -> None:
    """The bump scales linearly with ``speaker.KdF``."""
    speaker_lo = _reference_speaker()
    speaker_lo.KdF = 0.1
    speaker_hi = _reference_speaker()
    speaker_hi.KdF = 0.4

    frame = HLFrame(f0=120.0, an=1.0)
    base = HLState(f1c=100.0, agf=2.5)

    state_lo = HLState(f1c=100.0, agf=2.5)
    state_hi = HLState(f1c=100.0, agf=2.5)
    map_glottal_formants_not_f1(frame, speaker_lo, state_lo, LLFrameN())
    map_glottal_formants_not_f1(frame, speaker_hi, state_hi, LLFrameN())

    bump_lo = state_lo.f1c - base.f1c
    bump_hi = state_hi.f1c - base.f1c
    # The 4x KdF should give 4x bump.
    assert _close(bump_hi, 4 * bump_lo, eps=1e-5)


# ---- NF2 / NF3 / NF4 / NF5 ----------------------------------------------


def test_nf2_nf3_nf4_truncate_toward_zero() -> None:
    """``(short)`` cast truncates toward zero; we use ``int()``."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.0, an=10.0, f2=1234.7, f3=2500.2, f4=3450.99)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # Note: int() in Python truncates toward zero for positive values, matching (short).
    assert llframe.NF2 == 1234
    assert llframe.NF3 == 2500
    assert llframe.NF4 == 3450


def test_nf5_taken_from_speaker_not_frame() -> None:
    """``NF5`` is filled from ``speaker.F5``, not from any field on frame."""
    speaker = _reference_speaker()
    speaker.F5 = 3700.4
    frame = HLFrame(f0=120.0, an=10.0, f2=1.0, f3=2.0, f4=3.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    assert llframe.NF5 == 3700


def test_does_not_touch_unrelated_llframe_fields() -> None:
    """Only NF0/NF2/NF3/NF4/NF5 are written; other fields are left alone."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.0, an=10.0, f2=1500.0, f3=2500.0, f4=3500.0)
    state = HLState(f1c=400.0, agf=0.1)
    llframe = LLFrameN(NF1=550, NAV=42, NOQ=33, NB1=88, NAH=11, NAF=22)
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # These were not assigned by the helper.
    assert llframe.NF1 == 550
    assert llframe.NAV == 42
    assert llframe.NOQ == 33
    assert llframe.NB1 == 88
    assert llframe.NAH == 11
    assert llframe.NAF == 22


def test_does_not_touch_state_when_guards_fail() -> None:
    """When the f1c-bump guards fail, no field of state is modified."""
    speaker = _reference_speaker()
    frame = HLFrame(f0=120.0, an=10.0)  # an >= 3 -> outer guard fails
    state = HLState(f1c=100.0, agf=2.5, Pm=12.34, Ug=3.45)
    llframe = LLFrameN()
    map_glottal_formants_not_f1(frame, speaker, state, llframe)
    # f1c unchanged (outer guard failed) AND other state fields untouched.
    assert _close(state.f1c, 100.0)
    assert _close(state.Pm, 12.34)
    assert _close(state.Ug, 3.45)
    assert _close(state.agf, 2.5)
