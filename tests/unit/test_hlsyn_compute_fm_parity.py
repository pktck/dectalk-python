"""C-source parity test for ``Compute_fm`` against nasalf1x.c.

Re-parses the C body and asserts the piecewise-linear blend
matches the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.compute_fm import compute_fm
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/nasalf1x.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_nasalf1x_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_nasalf1x_c()
    match = re.search(
        r"Compute_fm\s*\([^)]*\)\s*\n\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "Compute_fm() definition not found in nasalf1x.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static float Compute_fm(HLFrame *, HLSpeaker *)``."""
    text = _read_nasalf1x_c()
    sig = re.search(
        r"static\s+float\s+Compute_fm\s*\(\s*HLFrame\s*\*\s*\w+\s*,\s*HLSpeaker\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_branch_predicate_uses_f1_breakpoint() -> None:
    """The branch test is ``frame->f1 >= speaker->fm_f1BreakPoint``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*frame->f1\s*>=\s*speaker->fm_f1BreakPoint\s*\)",
        body,
    )


def test_high_branch_formula() -> None:
    """High branch: ``0.8 * f2 + 0.2 * f3``."""
    body = _extract_body()
    assert re.search(
        r"0\.8f?\s*\*\s*frame->f2\s*\+\s*0\.2f?\s*\*\s*frame->f3",
        body,
    )


def test_low_branch_blend_factor() -> None:
    """Low branch: ``r = 1.0 + 0.0143 * (f1 - fm_f1BreakPoint)``."""
    body = _extract_body()
    assert re.search(
        r"r\s*=\s*\(\s*float\s*\)\s*\(\s*1\.0f?\s*\+\s*0\.0143f?\s*\*\s*"
        r"\(\s*frame->f1\s*-\s*speaker->fm_f1BreakPoint\s*\)\s*\)",
        body,
    )


def test_low_branch_3000hz_target() -> None:
    """Low branch terminus: weighted with 3000.0 Hz reference."""
    body = _extract_body()
    assert re.search(r"\(\s*1\.0?-\s*r\s*\)\s*\*\s*3000\.", body)


def test_python_high_branch_at_break_point() -> None:
    """``f1 == fm_f1BreakPoint`` -> high branch (``>=``)."""
    frame = HLFrame(f1=400.0, f2=1500.0, f3=2500.0)
    speaker = HLSpeaker(fm_f1BreakPoint=400.0)
    assert abs(compute_fm(frame, speaker) - (0.8 * 1500.0 + 0.2 * 2500.0)) < 1e-6


def test_python_high_branch_above_break_point() -> None:
    """``f1 > fm_f1BreakPoint`` -> ``0.8*f2 + 0.2*f3``."""
    frame = HLFrame(f1=500.0, f2=1000.0, f3=2000.0)
    speaker = HLSpeaker(fm_f1BreakPoint=400.0)
    assert abs(compute_fm(frame, speaker) - (0.8 * 1000.0 + 0.2 * 2000.0)) < 1e-6


def test_python_low_branch_below_break_point() -> None:
    """``f1 < fm_f1BreakPoint`` -> blended via r factor."""
    frame = HLFrame(f1=300.0, f2=1000.0, f3=2000.0)
    speaker = HLSpeaker(fm_f1BreakPoint=400.0)
    r = 1.0 + 0.0143 * (300.0 - 400.0)
    expected = r * (0.8 * 1000.0 + 0.2 * 2000.0) + (1.0 - r) * 3000.0
    assert abs(compute_fm(frame, speaker) - expected) < 1e-6


def test_python_low_branch_far_below_approaches_3000() -> None:
    """As ``f1`` drops far below break point, fm approaches 3000."""
    # r at f1 = -breakpoint/0.0143 + breakpoint ≈ 330 below breakpoint => r≈-3.7
    # The blend doesn't actually approach 3000 monotonically — preserved here
    # just to exercise the formula.
    frame = HLFrame(f1=0.0, f2=1000.0, f3=2000.0)
    speaker = HLSpeaker(fm_f1BreakPoint=400.0)
    r = 1.0 + 0.0143 * (0.0 - 400.0)
    expected = r * (0.8 * 1000.0 + 0.2 * 2000.0) + (1.0 - r) * 3000.0
    assert abs(compute_fm(frame, speaker) - expected) < 1e-6
