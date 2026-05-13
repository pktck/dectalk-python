"""C-source parity test for ``DT_f_sqrt`` against sqrttable.c.

Re-parses ``src/dapi/src/hlsyn/sqrttable.c``, asserts:

- The signature is ``float DT_f_sqrt(float input)``.
- The four range constants (``+/- 40000.0f``, ``+/- 400``) match the
  ones the Python port uses.
- The Linux-active slice of ``sqrttable[]`` (everything before the
  ``#if 0`` block at index 404) matches :data:`SQRTTABLE` verbatim.
- The first few hand-checked entries are sqrt(i) for i in [0, 16].

Then exercises :func:`dt_f_sqrt` across every branch of the lookup
(in-range positive/negative, the ``pos > 400`` divide-by-100 branch,
the ``|input| > 40000`` ``math.sqrt`` fallback) and asserts the
result is close to :func:`math.sqrt` within a tolerance commensurate
with the table's 1-unit step.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.sqrt_table import SQRTTABLE, dt_f_sqrt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/sqrttable.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_sqrttable_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _parse_linux_active_table() -> tuple[float, ...]:
    """Extract the Linux-active slice of ``sqrttable[]`` from sqrttable.c.

    Entries past index 403 sit inside a ``#if 0`` ... ``#endif`` block
    in the C source -- those are never compiled. We slice from the
    ``= {`` opening up to (but not including) the ``#if 0`` marker.
    """
    text = _read_sqrttable_c()
    match = re.search(
        r"sqrttable\[\]\s*=\s*\{(.+?)#if\s+0",
        text,
        re.DOTALL,
    )
    assert match is not None, "could not locate sqrttable[] before its #if 0 block"
    body = match.group(1)
    floats = re.findall(r"-?\d+\.\d+f", body)
    return tuple(float(s.rstrip("f")) for s in floats)


def test_signature_matches_c() -> None:
    """Signature is ``float DT_f_sqrt(float input)``."""
    text = _read_sqrttable_c()
    sig = re.search(r"float\s+DT_f_sqrt\s*\(\s*float\s+\w+\s*\)\s*\{", text)
    assert sig is not None


def test_range_constants_match_c() -> None:
    """The +/- 40000 and +/- 400 thresholds appear verbatim in the C source."""
    text = _read_sqrttable_c()
    # Outer math.sqrt fallback bounds.
    assert re.search(r"input\s*>\s*40000\.0f", text)
    assert re.search(r"input\s*<\s*-40000\.0f", text)
    # Inner divide-by-100 branch bounds.
    assert re.search(r"pos\s*>\s*400", text)
    assert re.search(r"pos\s*<\s*-400", text)


def test_dtsqrt_macro_aliases_dt_f_sqrt() -> None:
    """The C ``DTsqrt`` and ``FLOW_SQRT`` macros wrap ``DT_f_sqrt``.

    Defined in ``hlsyn.h`` alongside the ``DT_f_sqrt`` extern. We
    re-check the alias here so the docstring's claim is anchored to
    the C source rather than tribal knowledge.
    """
    header = _C_FILE.parent / "hlsyn.h"
    if not header.is_file():
        pytest.skip("hlsyn.h not present alongside sqrttable.c")
    text = header.read_bytes().replace(b"\r", b"").decode("latin-1")
    assert re.search(r"#define\s+DTsqrt\s*\(\s*x\s*\)\s*DT_f_sqrt\s*\(\s*x\s*\)", text)
    assert re.search(r"#define\s+FLOW_SQRT\s*\(\s*X\s*\)\s*DTsqrt\s*\(\s*X\s*\)", text)


def test_table_matches_c_linux_active_slice() -> None:
    """``SQRTTABLE`` is the verbatim Linux-active slice of ``sqrttable[]``."""
    parsed = _parse_linux_active_table()
    assert len(parsed) == len(SQRTTABLE), (
        f"length drift: parsed {len(parsed)} entries from C, SQRTTABLE has {len(SQRTTABLE)}"
    )
    assert parsed == SQRTTABLE


def test_table_size_is_404() -> None:
    """The compiled slice covers indices 0..403 (404 entries total).

    The lookup logic in ``DT_f_sqrt`` only indexes 0..400 (the inner
    branches divide the >400 case by 100), so the extra three entries
    are dead but harmless.
    """
    assert len(SQRTTABLE) == 404


def test_table_first_entries_are_exact_sqrts() -> None:
    """The first 17 entries are ``sqrt(0..16)`` to 8 decimals."""
    for i in range(17):
        assert abs(SQRTTABLE[i] - math.sqrt(i)) < 5e-9


def test_table_index_400_is_20() -> None:
    """``sqrttable[400] == sqrt(400) == 20`` exactly."""
    assert abs(SQRTTABLE[400] - 20.0) < 1e-9


# --------------------------------------------------------------------------
# Functional behaviour of the lookup wrapper.
# --------------------------------------------------------------------------


# Roughly the worst-case error for the 1-unit-step LUT in the
# ``0 <= pos <= 400`` branch. ``sqrt`` is locally Lipschitz with
# constant ~0.5 there, so a 1-unit input step is at most ~0.5 in
# the output -- plus a small float-rounding cushion.
_LUT_TOL_LOW: float = 0.6
# For the ``pos > 400`` branch the effective step is 100 units. The
# returned value is ``sqrttable[pos // 100] * 10``, which lands on
# ``sqrt(100 * (pos // 100))``; vs. true ``sqrt(input)`` the gap can
# reach roughly ~``sqrt(input) - sqrt(input - 100)`` ~ ``50 /
# sqrt(input)``. Bound that loosely.
_LUT_TOL_HIGH: float = 3.0


def test_dt_f_sqrt_zero() -> None:
    """``dt_f_sqrt(0)`` is 0."""
    assert dt_f_sqrt(0.0) == 0.0


def test_dt_f_sqrt_small_positives_match_math_sqrt() -> None:
    """Spot-check small positive inputs against :func:`math.sqrt`.

    Inputs that hit integer indices in ``[0, 400]`` return the exact
    table entry, which is ``sqrt(i)`` to 8 decimals.
    """
    for x in (1.0, 4.0, 16.0, 25.0, 100.0, 225.0, 400.0):
        assert abs(dt_f_sqrt(x) - math.sqrt(x)) < 5e-8


def test_dt_f_sqrt_low_range_truncates_index() -> None:
    """Non-integer inputs in ``[0, 400]`` use ``sqrttable[int(input)]``.

    The C source casts ``input`` to ``int`` (truncate-toward-zero)
    so e.g. ``dt_f_sqrt(2.9)`` returns ``sqrttable[2]``, NOT
    ``sqrt(2.9)``. We verify the LUT-style result here.
    """
    assert abs(dt_f_sqrt(2.9) - SQRTTABLE[2]) < 5e-9
    assert abs(dt_f_sqrt(2.0) - SQRTTABLE[2]) < 5e-9
    # And both are within the coarse Lipschitz bound vs math.sqrt.
    assert abs(dt_f_sqrt(2.9) - math.sqrt(2.9)) < _LUT_TOL_LOW


def test_dt_f_sqrt_negative_low_range() -> None:
    """``dt_f_sqrt(-x)`` for ``-400 <= -x <= 0`` returns ``-sqrttable[-pos]``.

    C: ``return -sqrttable[-pos];`` with ``pos = (int)(-x)``.
    """
    for x in (-1.0, -16.0, -100.0, -400.0):
        expected = -math.sqrt(-x)
        assert abs(dt_f_sqrt(x) - expected) < 5e-8


def test_dt_f_sqrt_high_range_uses_div100_branch() -> None:
    """Inputs in ``(400, 40000]`` go through the ``pos // 100`` branch.

    ``return sqrttable[pos / 100] * 10.0f``. For ``input = 900.0``
    that's ``sqrttable[9] * 10`` = ``3.0 * 10`` = ``30`` exactly,
    which matches ``sqrt(900)``.
    """
    assert abs(dt_f_sqrt(900.0) - 30.0) < 1e-8
    assert abs(dt_f_sqrt(2500.0) - 50.0) < 1e-8
    assert abs(dt_f_sqrt(40000.0) - 200.0) < 1e-8


def test_dt_f_sqrt_high_range_within_loose_tolerance() -> None:
    """Non-perfect-square inputs in ``(400, 40000]`` track ``math.sqrt``.

    The LUT is coarser here -- the step is 100 units -- but the
    returned value should still be in the right ballpark.
    """
    for x in (450.0, 1234.0, 12345.0, 39999.0):
        assert abs(dt_f_sqrt(x) - math.sqrt(x)) < _LUT_TOL_HIGH


def test_dt_f_sqrt_negative_high_range() -> None:
    """``dt_f_sqrt(-x)`` for ``x in (400, 40000]`` returns ``-sqrt`` approx."""
    for x in (900.0, 2500.0, 10000.0):
        assert abs(dt_f_sqrt(-x) - (-math.sqrt(x))) < 1e-7


def test_dt_f_sqrt_above_40000_uses_math_sqrt() -> None:
    """Inputs above 40000 fall back to :func:`math.sqrt`."""
    for x in (40001.0, 1.0e6, 1.0e9):
        assert abs(dt_f_sqrt(x) - math.sqrt(x)) < 1e-9


def test_dt_f_sqrt_below_negative_40000_uses_neg_math_sqrt() -> None:
    """Inputs below -40000 fall back to ``-math.sqrt(-input)``."""
    for x in (-40001.0, -1.0e6, -1.0e9):
        assert abs(dt_f_sqrt(x) - (-math.sqrt(-x))) < 1e-9


def test_dt_f_sqrt_boundary_input_eq_40000() -> None:
    """``input == 40000`` is NOT in the ``>40000`` branch.

    The C check is strict (``>``), so ``input == 40000`` falls
    through to the LUT branch (``pos = 40000``, ``pos / 100 = 400``,
    returns ``sqrttable[400] * 10 = 200``).
    """
    assert abs(dt_f_sqrt(40000.0) - 200.0) < 1e-8


def test_dt_f_sqrt_boundary_input_eq_neg_40000() -> None:
    """``input == -40000`` is symmetric: returns ``-200``."""
    assert abs(dt_f_sqrt(-40000.0) - (-200.0)) < 1e-8


def test_dt_f_sqrt_boundary_pos_eq_400() -> None:
    """``pos == 400`` (i.e. ``input`` in ``[400, 401)``) uses LUT directly.

    C: ``if (pos > 400)`` is FALSE for ``pos == 400``, so we land
    in the ``return sqrttable[pos]`` branch with ``sqrttable[400]
    = 20``.
    """
    assert abs(dt_f_sqrt(400.0) - 20.0) < 1e-9
    assert abs(dt_f_sqrt(400.5) - 20.0) < 1e-9


def test_dt_f_sqrt_boundary_pos_eq_neg_400() -> None:
    """``pos == -400`` is symmetric: returns ``-sqrttable[400] = -20``."""
    assert abs(dt_f_sqrt(-400.0) - (-20.0)) < 1e-9
