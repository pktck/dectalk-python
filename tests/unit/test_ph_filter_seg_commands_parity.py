"""C-source parity test for ``filter_seg_commands`` against ph_drwt02.c.

Re-parses the C body and asserts:

- The function signature matches ``static void filter_seg_commands(PDPH_T, short f0in)``.
- The first-pole filter uses ``f0sa1 * tarseg + f0sb * f0slas1`` and
  writes ``f0slas1``.
- The second-pole filter uses ``f0sa2 * (f0sout1 + tarseg1<<F0SHFT)
  + f0sb * f0slas2`` and writes ``f0slas2``.
- The final write is ``f0s = f0sout2 >> F0SHFT``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.filter_seg_commands import filter_seg_commands
from dectalk.ph.math_helpers import mlsh1

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_drwt02.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_drwt02_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_drwt02_c()
    match = re.search(
        r"static\s+void\s+filter_seg_commands\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "filter_seg_commands() not found in ph_drwt02.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void filter_seg_commands(PDPH_T, short)``."""
    text = _read_drwt02_c()
    sig = re.search(
        r"static\s+void\s+filter_seg_commands\s*\(\s*PDPH_T\s+\w+\s*,"
        r"\s*short\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_first_pole_filter() -> None:
    """First pole: ``f0sa1 * tarseg + f0sb * f0slas1`` → ``f0slas1``."""
    body = _extract_body()
    assert re.search(
        r"f0souta\s*=\s*mlsh1\s*\(\s*pDphsettar->f0sa1\s*,\s*pDphsettar->tarseg\s*\)",
        body,
    )
    assert re.search(
        r"f0soutb\s*=\s*mlsh1\s*\(\s*pDphsettar->f0sb\s*,\s*pDphsettar->f0slas1\s*\)",
        body,
    )
    assert re.search(r"f0sout1\s*=\s*f0souta\s*\+\s*f0soutb", body)
    assert re.search(r"pDphsettar->f0slas1\s*=\s*f0sout1\s*;", body)


def test_second_pole_filter() -> None:
    """Second pole: ``f0sa2 * (f0sout1 + tarseg1<<F0SHFT) + f0sb * f0slas2``."""
    body = _extract_body()
    assert re.search(
        r"f0soutc\s*=\s*mlsh1\s*\(\s*pDphsettar->f0sa2\s*,\s*"
        r"\(\s*f0sout1\s*\+\s*\(\s*pDphsettar->tarseg1\s*<<\s*F0SHFT\s*\)\s*\)\s*\)",
        body,
    )
    assert re.search(
        r"f0soutd\s*=\s*mlsh1\s*\(\s*pDphsettar->f0sb\s*,\s*pDphsettar->f0slas2\s*\)",
        body,
    )
    assert re.search(r"f0sout2\s*=\s*f0soutc\s*\+\s*f0soutd", body)
    assert re.search(r"pDphsettar->f0slas2\s*=\s*f0sout2\s*;", body)


def test_final_write_is_f0s_shifted() -> None:
    """``pDph_t->f0s = f0sout2 >> F0SHFT;``."""
    body = _extract_body()
    assert re.search(r"pDph_t->f0s\s*=\s*f0sout2\s*>>\s*F0SHFT\s*;", body)


def test_python_zeros_when_all_inputs_zero() -> None:
    """All-zero filter state → f0s stays zero."""
    state = DphT()
    settar = DphSettarSt()
    state.pSTphsettar = settar
    filter_seg_commands(state, 0)
    assert settar.f0slas1 == 0
    assert settar.f0slas2 == 0
    assert state.f0s == 0


def test_python_first_pole_step_response() -> None:
    """Step input: tarseg=100, f0sa1=8192 (=0.5 in Q14), f0sb=0 → f0slas1=...."""
    state = DphT()
    settar = DphSettarSt(f0sa1=8192, f0sa2=0, f0sb=0, tarseg=100, tarseg1=0)
    state.pSTphsettar = settar
    filter_seg_commands(state, 0)
    # f0souta = mlsh1(8192, 100) = (8192*100 + 8192) >> 14 = ~50
    # f0soutb = 0
    # f0sout1 = ~50
    assert settar.f0slas1 == mlsh1(8192, 100)
    # f0soutc = mlsh1(0, f0sout1 + 0) = 0
    # f0soutd = 0
    # f0sout2 = 0
    assert settar.f0slas2 == 0
    assert state.f0s == 0


def test_python_filter_state_accumulates_across_calls() -> None:
    """A second call sees the f0slas1/f0slas2 from the first."""
    state = DphT()
    settar = DphSettarSt(f0sa1=8192, f0sa2=8192, f0sb=8192, tarseg=100, tarseg1=0)
    state.pSTphsettar = settar
    filter_seg_commands(state, 0)
    first_f0slas1 = settar.f0slas1
    first_f0slas2 = settar.f0slas2
    # Second call: same tarseg, the feedback path should evolve f0slas2.
    filter_seg_commands(state, 0)
    # f0slas1 increases (more of the step accumulated)
    assert settar.f0slas1 != first_f0slas1
    # f0slas2 also evolves with the second-pole feedback
    assert settar.f0slas2 != first_f0slas2


def test_python_no_op_when_pdphsettar_missing() -> None:
    """Missing target struct → defensive early return."""
    state = DphT()
    state.pSTphsettar = None
    filter_seg_commands(state, 0)


def test_python_f0in_unused() -> None:
    """The ``f0in`` parameter is ignored: same output regardless of value."""
    state_a = DphT()
    state_b = DphT()
    settar_a = DphSettarSt(f0sa1=8192, tarseg=100)
    settar_b = DphSettarSt(f0sa1=8192, tarseg=100)
    state_a.pSTphsettar = settar_a
    state_b.pSTphsettar = settar_b
    filter_seg_commands(state_a, 0)
    filter_seg_commands(state_b, 12345)
    assert settar_a.f0slas1 == settar_b.f0slas1
    assert state_a.f0s == state_b.f0s
