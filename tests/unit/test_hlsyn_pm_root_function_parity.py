"""C-source parity test for ``PmRootFunction`` against circuit.c.

Re-parses ``src/dapi/src/hlsyn/circuit.c`` and asserts the Python
port :func:`pm_root_function` matches the C source structurally
and numerically:

- The ``PmRootFunctionArgs`` ``typedef struct`` declares exactly
  the twelve fields the Python dataclass exposes (in order).
- The ``PmRootFunction`` body has the ``agx0`` formula, the
  ``agx < 0 -> 0`` clamp, and the ``Uw - NEXT_Uw`` return.
- ``NEXT_Uw(Pm, p)`` expands to ``(p)->A * (Pm) - (p)->B``.
- A handful of reference (``Pm``, args) pairs match the
  re-implementation in this test file to better than 1e-9
  (which is well below the float-32 epsilon the C code runs at).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is
absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.pm_root_args import PmRootFunctionArgs
from dectalk.hlsyn.pm_root_function import pm_root_function
from dectalk.hlsyn.sqrt_table import dt_f_sqrt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/circuit.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_circuit_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_pm_root_function_body() -> str:
    """Return the body of ``PmRootFunction`` from circuit.c."""
    text = _read_circuit_c()
    match = re.search(
        r"static\s+float\s*\n\s*PmRootFunction\s*\([^)]*\)\s*\n\s*\{(.+?)^\s*\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "PmRootFunction() definition not found in circuit.c"
    return match.group(1)


# ---------------------------------------------------------------------------
# Structural parity: struct layout / function signature / body shape.
# ---------------------------------------------------------------------------


_EXPECTED_FIELDS: tuple[str, ...] = (
    "rootTwoOverRho",
    "ag",
    "acx",
    "an",
    "ap",
    "ue",
    "ps",
    "Lg",
    "Cg",
    "Cw",
    "A",
    "B",
)


def test_pm_root_function_args_struct_fields_match_c() -> None:
    """``PmRootFunctionArgs`` declares exactly the twelve C fields, in order."""
    text = _read_circuit_c()
    match = re.search(
        r"typedef\s+struct\s*\{(.+?)\}\s*PmRootFunctionArgs\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None, "PmRootFunctionArgs struct not found in circuit.c"
    body = match.group(1)

    # Extract field identifiers; each line is `float <name>;`.
    fields = tuple(re.findall(r"float\s+(\w+)\s*;", body))
    assert fields == _EXPECTED_FIELDS

    # And the Python dataclass has every one of them.
    args = PmRootFunctionArgs()
    for name in _EXPECTED_FIELDS:
        assert hasattr(args, name), f"PmRootFunctionArgs missing field {name!r}"


def test_pm_root_function_signature_matches_c() -> None:
    """Signature: ``static float PmRootFunction(float Pm, void* pVoidOtherArgs)``."""
    text = _read_circuit_c()
    sig = re.search(
        r"static\s+float\s*\n\s*PmRootFunction\s*\(\s*"
        r"float\s+Pm\s*,\s*void\s*\*\s*pVoidOtherArgs\s*\)\s*\n\s*\{",
        text,
    )
    assert sig is not None


def test_pm_root_function_agx0_formula_in_body() -> None:
    """``agx0 = pOtherArgs->ag + Pm * pOtherArgs->Cg * pOtherArgs->Lg``."""
    body = _extract_pm_root_function_body()
    assert re.search(
        r"agx0\s*=\s*pOtherArgs->ag\s*\+\s*Pm\s*\*\s*"
        r"pOtherArgs->Cg\s*\*\s*pOtherArgs->Lg",
        body,
    )


def test_pm_root_function_agf_clamps_negative_agx0_to_zero() -> None:
    """``agf = (agx0 < 0 ? 0 : agx0) + pOtherArgs->ap``."""
    body = _extract_pm_root_function_body()
    assert re.search(
        r"agf\s*=\s*\(\s*agx0\s*<\s*0\.0f\s*\?\s*0\.0f\s*:\s*agx0\s*\)\s*\+\s*"
        r"pOtherArgs->ap",
        body,
    )


def test_pm_root_function_uses_flow_sqrt_twice() -> None:
    """Body invokes ``FLOW_SQRT`` for the ``(ps - Pm)`` and ``(Pm)`` terms."""
    body = _extract_pm_root_function_body()
    assert re.search(r"agf\s*\*\s*FLOW_SQRT\s*\(\s*pOtherArgs->ps\s*-\s*Pm\s*\)", body)
    assert re.search(
        r"\(\s*pOtherArgs->acx\s*\+\s*pOtherArgs->an\s*\)\s*\*\s*FLOW_SQRT\s*\(\s*Pm\s*\)",
        body,
    )


def test_pm_root_function_returns_uw_minus_next_uw() -> None:
    """The return line is exactly ``Uw - NEXT_Uw(Pm, pOtherArgs)``."""
    body = _extract_pm_root_function_body()
    assert re.search(r"return\s+Uw\s*-\s*NEXT_Uw\s*\(\s*Pm\s*,\s*pOtherArgs\s*\)", body)


def test_next_uw_macro_definition_matches_python_inline() -> None:
    """``#define NEXT_Uw(Pm, p) ((p)->A * (Pm) - (p)->B)``."""
    text = _read_circuit_c()
    assert re.search(
        r"#define\s+NEXT_Uw\s*\(\s*Pm\s*,\s*p\s*\)\s*\\\s*\n\s*"
        r"\(\s*\(\s*p\s*\)\s*->\s*A\s*\*\s*\(\s*Pm\s*\)\s*-\s*\(\s*p\s*\)\s*->\s*B\s*\)",
        text,
    )


def test_root_two_over_rho_constant_present_in_circuit_c() -> None:
    """The pre-computed ``sqrt(2 / RHO)`` literal appears in circuit.c."""
    text = _read_circuit_c()
    assert "41.885390829169" in text


# ---------------------------------------------------------------------------
# Behavioural parity: reference values match the inline formula.
# ---------------------------------------------------------------------------

_ABS_TOL = 1e-9


def _expected_pm_root_function(pm: float, args: PmRootFunctionArgs) -> float:
    """Reference re-implementation in double precision, for the parity check."""
    agx0 = args.ag + pm * args.Cg * args.Lg
    agf = (0.0 if agx0 < 0.0 else agx0) + args.ap
    uw = -args.ue + args.rootTwoOverRho * (
        agf * dt_f_sqrt(args.ps - pm) - (args.acx + args.an) * dt_f_sqrt(pm)
    )
    return uw - (args.A * pm - args.B)


def _baseline_args() -> PmRootFunctionArgs:
    """A plausible mid-frame state with all fields exercised."""
    return PmRootFunctionArgs(
        rootTwoOverRho=41.885390829169,
        ag=0.05,
        acx=0.30,
        an=0.10,
        ap=0.05,
        ue=20.0,
        ps=8000.0,
        Lg=0.30,
        Cg=1.0e-6,
        Cw=2.0e-5,
        A=1.0e-3,
        B=5.0,
    )


def test_pm_root_function_matches_reference_at_typical_pm() -> None:
    """Spot-check at a few mid-range Pm values."""
    args = _baseline_args()
    for pm in (100.0, 500.0, 1500.0, 4000.0, 7500.0):
        got = pm_root_function(pm, args)
        expected = _expected_pm_root_function(pm, args)
        assert abs(got - expected) <= _ABS_TOL, f"Pm={pm}: got {got}, expected {expected}"


def test_pm_root_function_handles_negative_agx0() -> None:
    """When ``ag + Pm*Cg*Lg < 0``, the body uses ``agf = 0 + ap``."""
    args = _baseline_args()
    args.ag = -1.0  # Strongly negative; even with Pm*Cg*Lg > 0, agx0 stays negative.
    args.Cg = 0.0  # Force agx0 = ag < 0 unconditionally.
    pm = 1000.0
    got = pm_root_function(pm, args)
    # With agx0 = -1.0 < 0, agf = 0 + ap = 0.05.
    agf = args.ap
    uw = -args.ue + args.rootTwoOverRho * (
        agf * dt_f_sqrt(args.ps - pm) - (args.acx + args.an) * dt_f_sqrt(pm)
    )
    expected = uw - (args.A * pm - args.B)
    assert abs(got - expected) <= _ABS_TOL


def test_pm_root_function_handles_pm_greater_than_ps() -> None:
    """``Pm > ps`` makes ``FLOW_SQRT(ps - Pm) < 0`` -- mirrored by the LUT."""
    args = _baseline_args()
    pm = args.ps + 500.0  # negative argument to FLOW_SQRT.
    got = pm_root_function(pm, args)
    expected = _expected_pm_root_function(pm, args)
    assert abs(got - expected) <= _ABS_TOL
    # And the LUT's negative-input branch was actually exercised.
    assert dt_f_sqrt(args.ps - pm) < 0.0


def test_pm_root_function_zero_pm_uses_ps_term_only() -> None:
    """At ``Pm = 0`` the ``(acx+an)*FLOW_SQRT(Pm)`` term vanishes."""
    args = _baseline_args()
    got = pm_root_function(0.0, args)
    # agx0 = ag (since Pm = 0). agf = max(ag, 0) + ap.
    agf = (0.0 if args.ag < 0.0 else args.ag) + args.ap
    uw = -args.ue + args.rootTwoOverRho * agf * dt_f_sqrt(args.ps)
    expected = uw - (args.A * 0.0 - args.B)
    assert abs(got - expected) <= _ABS_TOL


def test_pm_root_function_zero_areas_simplifies_to_constants() -> None:
    """All-zero areas + zero ``ue`` -> the implicit-Euler ``-(A*Pm - B)`` term only."""
    args = PmRootFunctionArgs(
        rootTwoOverRho=41.885390829169,
        ag=0.0,
        acx=0.0,
        an=0.0,
        ap=0.0,
        ue=0.0,
        ps=5000.0,
        Lg=0.30,
        Cg=0.0,
        Cw=0.0,
        A=2.0e-3,
        B=1.5,
    )
    pm = 1000.0
    got = pm_root_function(pm, args)
    # Uw = -0 + rootTwoOverRho * (0 * sqrt(...) - 0 * sqrt(...)) = 0.
    expected = 0.0 - (args.A * pm - args.B)
    assert math.isclose(got, expected, rel_tol=1e-12, abs_tol=_ABS_TOL)


def test_pm_root_function_brackets_a_root() -> None:
    """For a plausible frame ``f(0) > 0`` and ``f(ps) < 0`` -- a root exists."""
    args = _baseline_args()
    # At Pm = 0: only the inflow ``agf*FLOW_SQRT(ps)`` minus ``ue`` contributes
    # to Uw; the -(A*Pm - B) = B addend pushes it further positive.
    f_lo = pm_root_function(0.0, args)
    # At Pm = ps: the inflow vanishes (FLOW_SQRT(0) = 0); the outflow goes
    # like -(acx+an)*sqrt(ps) and the implicit-Euler bias is -A*ps + B.
    f_hi = pm_root_function(args.ps, args)
    assert f_lo > 0.0
    assert f_hi < 0.0


def test_pm_root_function_strictly_decreases_with_pm_for_baseline() -> None:
    """For the baseline payload the target is monotonically decreasing in ``Pm``.

    This is what makes Brent's method tractable: a single sign change between
    the bracketing bounds. Any regression that swapped a sign would show up as
    a non-monotone sweep here.
    """
    args = _baseline_args()
    last = math.inf
    for pm in (0.0, 250.0, 750.0, 1500.0, 3000.0, 5000.0, 7000.0, 7800.0):
        value = pm_root_function(pm, args)
        assert value < last, f"non-monotone at Pm={pm}: {value} >= prev {last}"
        last = value
