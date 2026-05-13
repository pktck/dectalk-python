"""C-source parity test for the Helmholtz helpers against acxf1c.c.

Re-parses the bodies of ``HelmholtzFrequency`` and
``HelmholtzConstriction`` from ``src/dapi/src/hlsyn/acxf1c.c`` and
asserts each one:

- declares the expected signature,
- contains the load-bearing numeric constants
  (``1253160000.0f`` / ``39.478417604f`` for the forward
  function and ``3.150309426119e-8f`` for the inverse),
- delegates to ``DTsqrt`` in the forward direction.

Plus behavioural tests with reference inputs, including a forward
-> inverse round-trip that checks the two functions are algebraic
inverses of each other.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.helmholtz import helmholtz_constriction, helmholtz_frequency

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/acxf1c.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_acxf1c_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(name: str) -> str:
    """Return the body (between the outermost ``{`` and ``}``) of ``name``."""
    text = _read_acxf1c_c()
    match = re.search(
        rf"float\s+{re.escape(name)}\s*\([^)]*\)\s*\n\s*\{{(.+?)^\}}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{name}() definition not found in acxf1c.c"
    return match.group(1)


# ---------------------------------------------------------------------------
# Structural parity (signatures / constants / DTsqrt call).
# ---------------------------------------------------------------------------


def test_helmholtz_frequency_signature_matches_c() -> None:
    """Signature: ``float HelmholtzFrequency(float, float, float, float)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"float\s+HelmholtzFrequency\s*\(\s*"
        r"float\s+ConstrictionArea\s*,\s*"
        r"float\s+Volume\s*,\s*"
        r"float\s+Length\s*,\s*"
        r"float\s+ZeroAreaNaturalFrequency\s*\)\s*\n\s*\{",
        text,
    )
    assert sig is not None


def test_helmholtz_constriction_signature_matches_c() -> None:
    """Signature: ``float HelmholtzConstriction(float, float, float, float)``."""
    text = _read_acxf1c_c()
    sig = re.search(
        r"float\s+HelmholtzConstriction\s*\(\s*"
        r"float\s+LowestNaturalFrequency\s*,\s*"
        r"float\s+Volume\s*,\s*"
        r"float\s+Length\s*,\s*"
        r"float\s+ZeroAreaNaturalFrequency\s*\)\s*\n\s*\{",
        text,
    )
    assert sig is not None


def test_helmholtz_frequency_uses_speed_squared_and_four_pi_squared() -> None:
    """Body contains the ``SPEEDSOUND^2`` and ``4*pi^2`` literals."""
    body = _extract_body("HelmholtzFrequency")
    # SPEEDSOUND^2
    assert "1253160000.0f" in body
    # 4 * pi^2
    assert "39.478417604f" in body
    # And the dividend/divisor structure.
    assert re.search(
        r"temp\s*=\s*\(\s*float\s*\)\s*\(\s*"
        r"1253160000\.0f\s*\*\s*ConstrictionArea\s*/\s*\(\s*"
        r"39\.478417604f\s*\*\s*Volume\s*\*\s*Length\s*\)\s*\)\s*;",
        body,
    )


def test_helmholtz_frequency_returns_dtsqrt_of_sum() -> None:
    """Returns ``DTsqrt(temp + ZeroAreaNaturalFrequency^2)``."""
    body = _extract_body("HelmholtzFrequency")
    assert re.search(
        r"return\s*\(\s*float\s*\)\s*DTsqrt\s*\(\s*temp\s*\+\s*"
        r"ZeroAreaNaturalFrequency\s*\*\s*ZeroAreaNaturalFrequency\s*\)\s*;",
        body,
    )


def test_helmholtz_constriction_uses_inverse_constant() -> None:
    """Body contains the ``4*pi^2 / SPEEDSOUND^2`` literal."""
    body = _extract_body("HelmholtzConstriction")
    assert "3.150309426119e-8f" in body
    # And the multiplicative structure.
    assert re.search(
        r"temp\s*=\s*\(\s*float\s*\)\s*\(\s*"
        r"Volume\s*\*\s*Length\s*\*\s*3\.150309426119e-8f\s*\)\s*;",
        body,
    )


def test_helmholtz_constriction_returns_freq_squared_diff_times_temp() -> None:
    """Returns ``(LNF^2 - ZNF^2) * temp``."""
    body = _extract_body("HelmholtzConstriction")
    assert re.search(
        r"return\s*\(\s*\(\s*"
        r"LowestNaturalFrequency\s*\*\s*LowestNaturalFrequency\s*-\s*"
        r"ZeroAreaNaturalFrequency\s*\*\s*ZeroAreaNaturalFrequency\s*\)\s*\*\s*temp\s*\)\s*;",
        body,
    )


# ---------------------------------------------------------------------------
# Behavioural tests with reference inputs.
# ---------------------------------------------------------------------------


def _expected_helmholtz_frequency(ac: float, v: float, le: float, znf: float) -> float:
    """Re-implementation of the C formula, in double precision, for the test."""
    temp = 1253160000.0 * ac / (39.478417604 * v * le)
    return math.sqrt(temp + znf * znf)


def _expected_helmholtz_constriction(lnf: float, v: float, le: float, znf: float) -> float:
    """Re-implementation of the C formula, in double precision, for the test."""
    return (lnf * lnf - znf * znf) * (v * le * 3.150309426119e-8)


def test_helmholtz_frequency_matches_reference_formula() -> None:
    """Spot-check a handful of CGS-scale tuples against the bare formula."""
    cases = [
        (0.5, 60.0, 1.5, 200.0),
        (1.0, 60.0, 1.5, 200.0),
        (2.0, 60.0, 1.5, 200.0),
        (0.5, 90.0, 1.5, 200.0),
        (0.5, 60.0, 3.0, 200.0),
        (0.5, 60.0, 1.5, 400.0),
    ]
    for ac, v, le, znf in cases:
        got = helmholtz_frequency(ac, v, le, znf)
        expected = _expected_helmholtz_frequency(ac, v, le, znf)
        assert math.isclose(got, expected, rel_tol=1e-12, abs_tol=1e-9)


def test_helmholtz_constriction_matches_reference_formula() -> None:
    """Spot-check the inverse formula on the same shapes."""
    cases = [
        (500.0, 60.0, 1.5, 200.0),
        (800.0, 60.0, 1.5, 200.0),
        (1500.0, 60.0, 1.5, 200.0),
        (500.0, 90.0, 1.5, 200.0),
        (500.0, 60.0, 3.0, 200.0),
        (500.0, 60.0, 1.5, 400.0),
    ]
    for lnf, v, le, znf in cases:
        got = helmholtz_constriction(lnf, v, le, znf)
        expected = _expected_helmholtz_constriction(lnf, v, le, znf)
        assert math.isclose(got, expected, rel_tol=1e-12, abs_tol=1e-9)


def test_helmholtz_zero_area_returns_zero_area_natural_frequency() -> None:
    """At constriction area = 0, the resonator frequency collapses to ZNF."""
    znf = 250.0
    f = helmholtz_frequency(0.0, 60.0, 1.5, znf)
    assert math.isclose(f, znf, rel_tol=1e-12)


def test_helmholtz_constriction_zero_when_lnf_equals_znf() -> None:
    """At LNF = ZNF, the inverse yields zero constriction area."""
    ac = helmholtz_constriction(250.0, 60.0, 1.5, 250.0)
    assert math.isclose(ac, 0.0, abs_tol=1e-12)


def test_helmholtz_forward_inverse_roundtrip() -> None:
    """``constriction(frequency(ac)) == ac`` for non-degenerate inputs."""
    volume = 60.0
    length = 1.5
    znf = 200.0
    for ac in (0.1, 0.5, 1.0, 2.0, 5.0, 10.0):
        f = helmholtz_frequency(ac, volume, length, znf)
        ac_back = helmholtz_constriction(f, volume, length, znf)
        assert math.isclose(ac_back, ac, rel_tol=1e-9, abs_tol=1e-12)


def test_helmholtz_inverse_forward_roundtrip() -> None:
    """``frequency(constriction(f)) == f`` for ``f > znf``."""
    volume = 60.0
    length = 1.5
    znf = 200.0
    for lnf in (250.0, 500.0, 800.0, 1500.0, 3000.0):
        ac = helmholtz_constriction(lnf, volume, length, znf)
        lnf_back = helmholtz_frequency(ac, volume, length, znf)
        assert math.isclose(lnf_back, lnf, rel_tol=1e-9, abs_tol=1e-12)


def test_helmholtz_frequency_monotonic_in_constriction_area() -> None:
    """Larger constriction area => higher resonator frequency (fixed cavity)."""
    volume = 60.0
    length = 1.5
    znf = 200.0
    last = -math.inf
    for ac in (0.0, 0.1, 0.5, 1.0, 2.0, 5.0):
        f = helmholtz_frequency(ac, volume, length, znf)
        assert f > last
        last = f


def test_helmholtz_constants_match_physical_meaning() -> None:
    """The two constants are reciprocals (within double precision)."""
    # SPEEDSOUND^2 / (4 * pi^2) * (4 * pi^2 / SPEEDSOUND^2) == 1
    forward = 1253160000.0 / 39.478417604
    inverse = 3.150309426119e-8
    assert math.isclose(forward * inverse, 1.0, rel_tol=1e-9)
