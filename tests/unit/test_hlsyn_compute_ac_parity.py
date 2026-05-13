"""C-source parity tests for ``Compute_acl`` / ``Compute_acd`` against acxf1c.c.

Re-parses the C bodies and asserts:

- :func:`compute_acl` returns ``UNCOMPUTABLE`` outside the speaker's
  liquid range and the quadratic ``(f1 / aclFreq)^2 * Kacl`` inside.
- :func:`compute_acd` switches at ``acd_f1Break`` between the
  Helmholtz-resonator inverse (below) and the high-frequency
  quadratic (above), then clamps to ``[0, acdMax]``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.compute_ac import compute_acd, compute_acl
from dectalk.hlsyn.helmholtz import helmholtz_constriction
from dectalk.hlsyn.place_constants import UNCOMPUTABLE
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/acxf1c.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_acxf1c_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(func_name: str) -> str:
    text = _read_acxf1c_c()
    match = re.search(
        rf"float\s+{re.escape(func_name)}\s*\([^)]*\)\s*\n\s*\{{(.+?)^\}}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{func_name}() definition not found in acxf1c.c"
    return match.group(1)


# --------------------------------------------------------------------------
# Signature / structural parity.
# --------------------------------------------------------------------------


def test_compute_acl_signature_matches_c() -> None:
    """Signature is ``float Compute_acl(HLFrame *, HLSpeaker *)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"float\s+Compute_acl\s*\(\s*HLFrame\s*\*\s*\w+\s*,\s*HLSpeaker\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_compute_acd_signature_matches_c() -> None:
    """Signature is ``float Compute_acd(HLFrame *, HLSpeaker *)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"float\s+Compute_acd\s*\(\s*HLFrame\s*\*\s*\w+\s*,\s*HLSpeaker\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_compute_acl_f1_range_guard() -> None:
    """The ``f1Min < f1 < f1Max`` guard appears in the C body verbatim."""
    body = _extract_body("Compute_acl")
    assert re.search(
        r"speaker->f1Min\s*<\s*frame->f1\s*&&\s*frame->f1\s*<\s*speaker->f1Max",
        body,
    )


def test_compute_acl_retroflex_clause() -> None:
    """Retroflex sub-clause uses ``f2 < f2RetroflexMax && f3 < f3RetroflexMax``."""
    body = _extract_body("Compute_acl")
    assert re.search(
        r"frame->f2\s*<\s*speaker->f2RetroflexMax\s*&&\s*"
        r"frame->f3\s*<\s*speaker->f3RetroflexMax",
        body,
    )


def test_compute_acl_lateral_clause() -> None:
    """Lateral sub-clause uses ``f2 < f2LateralMax && f3 > f3LateralMin``."""
    body = _extract_body("Compute_acl")
    assert re.search(
        r"frame->f2\s*<\s*speaker->f2LateralMax\s*&&\s*"
        r"frame->f3\s*>\s*speaker->f3LateralMin",
        body,
    )


def test_compute_acl_quadratic_form() -> None:
    """In-range return is ``(f1/aclFreq)^2 * Kacl``."""
    body = _extract_body("Compute_acl")
    assert re.search(
        r"\(frame->f1\s*/\s*speaker->aclFreq\)\s*\*\s*"
        r"\(frame->f1\s*/\s*speaker->aclFreq\)\s*\*\s*speaker->Kacl",
        body,
    )


def test_compute_acl_out_of_range_returns_uncomputable() -> None:
    """The ``else`` branch returns ``UNCOMPUTABLE``."""
    body = _extract_body("Compute_acl")
    assert re.search(r"else\s*\n?\s*return\s+UNCOMPUTABLE", body)


def test_compute_acd_break_branch() -> None:
    """Below ``acd_f1Break`` -> ``HelmholtzConstriction`` then ``CMSQ_TO_MMSQ``."""
    body = _extract_body("Compute_acd")
    assert re.search(r"frame->f1\s*<\s*speaker->acd_f1Break", body)
    assert re.search(
        r"HelmholtzConstriction\s*\(\s*frame->f1\s*,\s*speaker->Vacd\s*,\s*"
        r"speaker->Lc_acd\s*,\s*speaker->HelmholtzZeroAreaFrequency",
        body,
    )
    assert "CMSQ_TO_MMSQ(acd)" in body


def test_compute_acd_high_branch() -> None:
    """Above the break -> quadratic in ``(f1HiShift - f1) / HelmholtzZeroAreaFrequency``."""
    body = _extract_body("Compute_acd")
    assert re.search(
        r"\(\s*speaker->f1HiShift\s*-\s*frame->f1\s*\)\s*"
        r"/\s*speaker->HelmholtzZeroAreaFrequency",
        body,
    )
    assert re.search(r"speaker->KHi\s*\*\s*temp\s*\*\s*temp\s*-\s*speaker->KHi", body)


def test_compute_acd_clamps_high() -> None:
    """``acd > acdMax`` returns ``acdMax``."""
    body = _extract_body("Compute_acd")
    assert re.search(r"acd\s*>\s*speaker->acdMax", body)
    assert re.search(r"return\s+speaker->acdMax", body)


def test_compute_acd_clamps_low() -> None:
    """``acd < 0.0`` returns ``0``."""
    body = _extract_body("Compute_acd")
    assert re.search(r"acd\s*<\s*0\.0", body)
    assert re.search(r"return\s+0\.f", body)


def test_helmholtz_constriction_constant_in_c() -> None:
    """The inlined Helmholtz constant ``3.150309426119e-8`` matches the C source."""
    text = _read_acxf1c_c()
    assert "3.150309426119e-8" in text


def test_cmsq_to_mmsq_macro_is_times_100() -> None:
    """``CMSQ_TO_MMSQ(x) = x * 100.0f`` per hlsyn.h."""
    hlsyn_h = _C_FILE.parent / "hlsyn.h"
    text = hlsyn_h.read_bytes().replace(b"\r", b"").decode("latin-1")
    assert re.search(r"CMSQ_TO_MMSQ\(CMSQ\)\s*\(\s*\(CMSQ\)\s*\*\s*100\.0f\s*\)", text)


# --------------------------------------------------------------------------
# Behavioural parity.
# --------------------------------------------------------------------------


def _liquid_speaker() -> HLSpeaker:
    """A speaker whose retroflex/lateral ranges admit liquid frames."""
    return HLSpeaker(
        f1Min=200.0,
        f1Max=600.0,
        f2RetroflexMax=1500.0,
        f3RetroflexMax=2000.0,
        f2LateralMax=1800.0,
        f3LateralMin=2500.0,
        aclFreq=400.0,
        Kacl=2.0,
    )


def test_compute_acl_retroflex_in_range() -> None:
    """Retroflex frame -> quadratic ``(f1/aclFreq)^2 * Kacl``."""
    speaker = _liquid_speaker()
    frame = HLFrame(f1=400.0, f2=1200.0, f3=1500.0)
    expected = (400.0 / 400.0) ** 2 * 2.0  # = 2.0
    assert abs(compute_acl(frame, speaker) - expected) < 1e-9


def test_compute_acl_lateral_in_range() -> None:
    """Lateral frame (low f2, high f3) -> quadratic form."""
    speaker = _liquid_speaker()
    frame = HLFrame(f1=300.0, f2=1500.0, f3=2800.0)
    expected = (300.0 / 400.0) ** 2 * 2.0
    assert abs(compute_acl(frame, speaker) - expected) < 1e-9


def test_compute_acl_below_f1_min_uncomputable() -> None:
    """``f1 <= f1Min`` -> ``UNCOMPUTABLE``."""
    speaker = _liquid_speaker()
    frame = HLFrame(f1=150.0, f2=1200.0, f3=1500.0)
    assert compute_acl(frame, speaker) == UNCOMPUTABLE


def test_compute_acl_above_f1_max_uncomputable() -> None:
    """``f1 >= f1Max`` -> ``UNCOMPUTABLE``."""
    speaker = _liquid_speaker()
    frame = HLFrame(f1=700.0, f2=1200.0, f3=1500.0)
    assert compute_acl(frame, speaker) == UNCOMPUTABLE


def test_compute_acl_f1_at_boundary_uncomputable() -> None:
    """Strict inequalities: ``f1 == f1Min`` -> ``UNCOMPUTABLE``."""
    speaker = _liquid_speaker()
    frame = HLFrame(f1=200.0, f2=1200.0, f3=1500.0)
    assert compute_acl(frame, speaker) == UNCOMPUTABLE


def test_compute_acl_outside_both_liquid_regions() -> None:
    """In f1 range but neither retroflex nor lateral region -> ``UNCOMPUTABLE``.

    High ``f2`` (above both max) puts the frame out of both regions.
    """
    speaker = _liquid_speaker()
    frame = HLFrame(f1=400.0, f2=2000.0, f3=1500.0)
    assert compute_acl(frame, speaker) == UNCOMPUTABLE


def test_compute_acl_retroflex_fails_on_high_f3() -> None:
    """Retroflex needs ``f3 < f3RetroflexMax``; this frame fails that
    and isn't lateral either (``f3 < f3LateralMin``)."""
    speaker = _liquid_speaker()
    # f2=1200 < f2RetroflexMax(1500), but f3=2100 >= f3RetroflexMax(2000).
    # f3=2100 < f3LateralMin(2500), so lateral also fails.
    frame = HLFrame(f1=400.0, f2=1200.0, f3=2100.0)
    assert compute_acl(frame, speaker) == UNCOMPUTABLE


def _acd_speaker() -> HLSpeaker:
    """A speaker with both Helmholtz and high-frequency branches workable."""
    return HLSpeaker(
        Vacd=50.0,
        Lc_acd=4.0,
        HelmholtzZeroAreaFrequency=200.0,
        acd_f1Break=600.0,
        f1HiShift=900.0,
        KHi=10.0,
        acdMax=400.0,
    )


def test_compute_acd_below_break_uses_helmholtz() -> None:
    """Below ``acd_f1Break``: matches the inlined Helmholtz form * 100."""
    speaker = _acd_speaker()
    frame = HLFrame(f1=500.0)  # < 600
    helm = helmholtz_constriction(500.0, 50.0, 4.0, 200.0)
    expected = helm * 100.0  # CMSQ_TO_MMSQ
    # Within [0, acdMax].
    assert 0.0 <= expected <= speaker.acdMax
    assert abs(compute_acd(frame, speaker) - expected) < 1e-6


def test_compute_acd_above_break_uses_quadratic() -> None:
    """Above ``acd_f1Break``: ``KHi * temp^2 - KHi`` with ``temp = (f1HiShift - f1)/Hz0``."""
    speaker = _acd_speaker()
    frame = HLFrame(f1=700.0)  # > 600
    temp = (speaker.f1HiShift - frame.f1) / speaker.HelmholtzZeroAreaFrequency
    expected = speaker.KHi * temp * temp - speaker.KHi
    # Within [0, acdMax].
    assert 0.0 <= expected <= speaker.acdMax
    assert abs(compute_acd(frame, speaker) - expected) < 1e-6


def test_compute_acd_clamps_to_acd_max() -> None:
    """A frame producing acd > acdMax clamps to ``acdMax``."""
    speaker = _acd_speaker()
    # Use a frame above the break with a small (f1HiShift - f1)/Hz0 -> negative => clamp low.
    # To force > acdMax: choose below-break with large f1.
    speaker.acdMax = 1.0  # very low cap
    frame = HLFrame(f1=500.0)
    helm = helmholtz_constriction(500.0, 50.0, 4.0, 200.0) * 100.0
    assert helm > speaker.acdMax
    assert abs(compute_acd(frame, speaker) - speaker.acdMax) < 1e-6


def test_compute_acd_clamps_to_zero() -> None:
    """A frame producing negative acd clamps to ``0``."""
    speaker = _acd_speaker()
    # Above break, with f1 == f1HiShift -> temp = 0 -> acd = -KHi < 0.
    frame = HLFrame(f1=speaker.f1HiShift)
    raw = speaker.KHi * 0.0 * 0.0 - speaker.KHi
    assert raw < 0.0
    assert compute_acd(frame, speaker) == 0.0


def test_compute_acd_at_break_uses_high_branch() -> None:
    """``f1 == acd_f1Break`` falls into the ``else`` branch (strict ``<``)."""
    speaker = _acd_speaker()
    frame = HLFrame(f1=speaker.acd_f1Break)
    temp = (speaker.f1HiShift - frame.f1) / speaker.HelmholtzZeroAreaFrequency
    expected = speaker.KHi * temp * temp - speaker.KHi
    if expected < 0.0:
        expected = 0.0
    elif expected > speaker.acdMax:
        expected = speaker.acdMax
    assert abs(compute_acd(frame, speaker) - expected) < 1e-6


def test_compute_acd_high_branch_negative_temp_squared_positive() -> None:
    """Above ``f1HiShift``: ``temp`` is negative but ``temp^2`` is positive."""
    speaker = _acd_speaker()
    frame = HLFrame(f1=1200.0)  # > f1HiShift=900
    temp = (speaker.f1HiShift - frame.f1) / speaker.HelmholtzZeroAreaFrequency
    assert temp < 0.0
    raw = speaker.KHi * temp * temp - speaker.KHi
    expected = max(0.0, min(raw, speaker.acdMax))
    assert abs(compute_acd(frame, speaker) - expected) < 1e-6


def test_compute_acd_helmholtz_constant_matches_c_value() -> None:
    """Inlined ``3.150309426119e-8`` agrees with ``4*pi^2 / SPEEDSOUND^2`` to about 8 digits.

    ``SPEEDSOUND = 35400 cm/s`` in the C source (``hlsyn.h``); the
    constant is the reciprocal-grouping that appears in
    ``HelmholtzConstriction`` (``Volume * Length * 4*pi^2 / c^2``).
    """
    expected = 4.0 * math.pi * math.pi / (35400.0 * 35400.0)
    assert abs(expected - 3.150309426119e-8) < 5e-12
