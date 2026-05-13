"""C-source parity test for ``filter_commands`` against ph_drwt02.c.

Re-parses the C body and asserts:

- The function signature matches ``static void filter_commands(PDPH_T, short f0in)``.
- The single active statement is ``pDph_t->f0 += (f0in - pDph_t->f0) >> 2``.
- All other filter logic (cascaded two-pole IIR) is commented out
  and therefore inactive — guards against an accidental "uncomment"
  by a future translator.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.filter_commands import filter_commands

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
        r"static\s+void\s+filter_commands\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "filter_commands() not found in ph_drwt02.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void filter_commands(PDPH_T, short f0in)``."""
    text = _read_drwt02_c()
    sig = re.search(
        r"static\s+void\s+filter_commands\s*\(\s*PDPH_T\s+\w+\s*,"
        r"\s*short\s+f0in\s*\)",
        text,
    )
    assert sig is not None


def test_active_statement_is_first_order_smoother() -> None:
    """The only active statement is ``pDph_t->f0 += (f0in - pDph_t->f0) >> 2;``."""
    body = _extract_body()
    # Strip all C comments so only active statements remain.
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    # Strip #if 0 ... #endif blocks (also dead code in the C body).
    stripped = re.sub(r"#if\s+0.*?#endif", "", stripped, flags=re.DOTALL)
    # The single active statement must be the smoother.
    assert re.search(
        r"pDph_t->f0\s*\+=\s*\(\s*f0in\s*-\s*pDph_t->f0\s*\)\s*>>\s*2\s*;",
        stripped,
    )


def test_no_other_active_f0_writes() -> None:
    """No active statement writes ``f0las1`` / ``f0las2`` (cascaded-pole code is dead)."""
    body = _extract_body()
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    stripped = re.sub(r"#if\s+0.*?#endif", "", stripped, flags=re.DOTALL)
    # No active assignment to f0las1 or f0las2 (two-pole state).
    assert "pDphsettar->f0las1" not in stripped
    assert "pDphsettar->f0las2" not in stripped


def test_python_no_op_when_f0_equals_f0in() -> None:
    """Steady state: f0in == f0 → no change."""
    state = DphT()
    state.f0 = 200
    filter_commands(state, 200)
    assert state.f0 == 200


def test_python_first_order_smoother_step() -> None:
    """Step input: f0=100, f0in=200 → f0 = 100 + (200-100)>>2 = 125."""
    state = DphT()
    state.f0 = 100
    filter_commands(state, 200)
    assert state.f0 == 125


def test_python_negative_delta_arithmetic_shift() -> None:
    """Negative delta: f0=200, f0in=100 → delta=-100, -100>>2=-25 → f0=175."""
    state = DphT()
    state.f0 = 200
    filter_commands(state, 100)
    # Python's >> on negative ints rounds toward negative infinity,
    # same as C on two's-complement architectures: -100 >> 2 == -25.
    assert state.f0 == 175


def test_python_zero_delta_at_zero_input() -> None:
    """f0=0, f0in=0 → f0 stays 0."""
    state = DphT()
    state.f0 = 0
    filter_commands(state, 0)
    assert state.f0 == 0


def test_python_converges_after_repeated_application() -> None:
    """Applying repeatedly approaches the input value (geometric decay)."""
    state = DphT()
    state.f0 = 0
    for _ in range(100):
        filter_commands(state, 100)
    # Integer arithmetic-shift-right truncates: once ``f0in - f0`` is
    # less than 4 the smoother stops advancing (delta>>2 == 0). The
    # asymptote settles a few units below the target.
    assert 95 <= state.f0 <= 100
