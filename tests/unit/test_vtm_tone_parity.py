"""C-source parity test for ``Tone`` against playtone.c.

Re-parses the C body and asserts the structural translation that
:func:`dectalk.vtm.tone.tone` (LOWCOMPUTE branch) and
:func:`dectalk.vtm.tone.tone_exact` (non-LOWCOMPUTE branch) implement:

- Signature: ``static double Tone(double PhaseIncrement, double *pPhase)``.
- LOWCOMPUTE branch reads ``SineTable[(int)*pPhase]``.
- Non-LOWCOMPUTE branch calls ``sin(*pPhase)``.
- ``*pPhase += PhaseIncrement`` advances the phase in place.
- ``if (*pPhase >= TWO_PI_EQUIVALENT) *pPhase -= TWO_PI_EQUIVALENT``
  wraps the phase back into ``[0, TWO_PI_EQUIVALENT)``.
- ``return Sample`` is the final statement.

Behaviour parity is covered by ``test_vtm_tone.py``; this test pins the
*shape* of the translation against the C source so a future drift in
either side surfaces immediately.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.sinetab import TWO_PI_EQUIVALENT, SineTable
from dectalk.vtm.tone import tone, tone_exact

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/vtm/playtone.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_playtone_c() -> str:
    """Read playtone.c with CRLF line endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the ``Tone`` function (between the outer braces)."""
    text = _read_playtone_c()
    match = re.search(
        r"static\s+double\s+Tone\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "Tone() not found in playtone.c"
    return match.group(1)


# --------------------------------------------------------------------------
# Structural parity: the C body matches the Python translation shape.
# --------------------------------------------------------------------------


def test_signature_matches_c() -> None:
    """Signature is ``static double Tone(double PhaseIncrement, double *pPhase)``."""
    text = _read_playtone_c()
    sig = re.search(
        r"static\s+double\s+Tone\s*\(\s*double\s+PhaseIncrement\s*,"
        r"\s*double\s*\*\s*pPhase\s*\)",
        text,
    )
    assert sig is not None, "Tone signature drifted from C source"


def test_lowcompute_branch_reads_sine_table() -> None:
    """The LOWCOMPUTE branch is ``Sample = SineTable[(int)*pPhase];``."""
    body = _extract_body()
    assert re.search(r"#ifdef\s+LOWCOMPUTE", body)
    assert re.search(
        r"Sample\s*=\s*SineTable\s*\[\s*\(\s*int\s*\)\s*\*\s*pPhase\s*\]\s*;",
        body,
    )


def test_non_lowcompute_branch_calls_sin() -> None:
    """The ``#else`` branch is ``Sample = sin(*pPhase);``."""
    body = _extract_body()
    assert re.search(r"#else", body)
    assert re.search(r"Sample\s*=\s*sin\s*\(\s*\*\s*pPhase\s*\)\s*;", body)
    assert re.search(r"#endif", body)


def test_phase_advances_in_place() -> None:
    """``*pPhase += PhaseIncrement;`` advances the phase."""
    body = _extract_body()
    assert re.search(r"\*\s*pPhase\s*\+=\s*PhaseIncrement\s*;", body)


def test_phase_wraps_at_two_pi_equivalent() -> None:
    """``if (*pPhase >= TWO_PI_EQUIVALENT) *pPhase -= TWO_PI_EQUIVALENT;``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*\*\s*pPhase\s*>=\s*TWO_PI_EQUIVALENT\s*\)",
        body,
    )
    assert re.search(r"\*\s*pPhase\s*-=\s*TWO_PI_EQUIVALENT\s*;", body)


def test_returns_sample() -> None:
    """The final statement is ``return( Sample );``."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*Sample\s*\)\s*;", body)


def test_body_has_no_other_statements() -> None:
    """Strip comments / ``#`` directives and check the active body is minimal.

    The active LOWCOMPUTE branch (the path the Linux build compiles) is
    exactly six statements:

    1. ``double Sample;``
    2. ``Sample = SineTable[(int)*pPhase];``
    3. ``*pPhase += PhaseIncrement;``
    4. ``if (*pPhase >= TWO_PI_EQUIVALENT)``
    5. ``    *pPhase -= TWO_PI_EQUIVALENT;``
    6. ``return( Sample );``

    Any extra side effect added on either side would break this count
    and force a deliberate update to the Python port (or to this test).
    """
    body = _extract_body()
    # Strip block / line comments and ``#...`` lines, then collapse blanks.
    no_block = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    no_cpp = re.sub(r"^\s*#.*$", "", no_line, flags=re.MULTILINE)
    # Drop the non-LOWCOMPUTE branch so the count reflects the Linux build.
    # The ``#else`` block contains exactly one line we want to ignore.
    no_else = re.sub(r"Sample\s*=\s*sin\s*\(\s*\*\s*pPhase\s*\)\s*;", "", no_cpp)
    # Statement-terminator + close-paren count is a faithful proxy.
    semis = no_else.count(";")
    # 5 ';'-terminated statements; the `if (...)` line itself is paren-only.
    # 1 declaration + 1 SineTable read + 1 += + 1 -= + 1 return = 5
    assert semis == 5, (
        f"Tone body shape changed: expected 5 statements (LOWCOMPUTE branch), "
        f"got {semis}. New body:\n{no_else}"
    )


# --------------------------------------------------------------------------
# Behavioural cross-checks: the Python port reproduces the C semantics on
# representative inputs. (Numerical parity in depth lives in
# ``test_vtm_tone.py``; here we just confirm the three observable effects.)
# --------------------------------------------------------------------------


def test_python_lowcompute_returns_sine_table_lookup() -> None:
    """``tone`` returns ``SineTable[int(phase)]`` (the LOWCOMPUTE C branch)."""
    sample, _ = tone(1.0, 100.5)
    assert sample == SineTable[100]


def test_python_phase_advances_by_increment() -> None:
    """The returned new_phase = phase + increment when below the wrap boundary."""
    _, new_phase = tone(5.5, 100.0)
    assert new_phase == 105.5


def test_python_phase_wraps_at_two_pi_equivalent() -> None:
    """Phase wraps when phase + increment >= TWO_PI_EQUIVALENT."""
    _, new_phase = tone(10.0, 1020.0)
    # 1020 + 10 = 1030 >= 1024, so subtract once.
    assert new_phase == 1030.0 - TWO_PI_EQUIVALENT


def test_python_tone_exact_uses_math_sin() -> None:
    """``tone_exact`` matches the non-LOWCOMPUTE C branch (``sin(*pPhase)``)."""
    sample, _ = tone_exact(0.1, math.pi / 4)
    assert sample == math.sin(math.pi / 4)
