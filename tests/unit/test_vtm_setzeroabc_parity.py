"""C-source parity test for :func:`setzeroabc` against vtm3.c.

Re-parses ``src/dapi/src/vtm/vtm3.c`` and asserts:

- The function signature matches
  ``void setzeroabc(int f, int bw, int rnzg, short *sacoef, short *sbcoef, short *sccoef)``.
- The 4-step coefficient computation appears in order:
  ``r = radius_table[bw >> 3]``, ``ccoef = -frac4mul(r, r)``,
  ``bcoef = frac4mul(r, cosine_table[f >> 3])``,
  ``acoef = 4096 - bcoef - ccoef``.
- The 3 output writes use the antiresonator formulas
  (a' = 1/a, b' = -b/a, c' = -c/a) scaled by ``rnzg``.

Plus behavioural tests pinning known (f, bw, rnzg) inputs to their
expected output coefficients, computed by hand from the
:data:`radius_table` / :data:`cosine_table` and the C
truncate-toward-zero division.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.cosine_radius_tables import cosine_table, radius_table
from dectalk.vtm.frac import frac4mul
from dectalk.vtm.setzeroabc import setzeroabc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtm3.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtm3_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``setzeroabc`` from vtm3.c (between the outermost braces)."""
    text = _read_vtm3_c()
    match = re.search(
        r"void\s+setzeroabc\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "setzeroabc() not found in vtm3.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature: ``void setzeroabc(int, int, int, short *, short *, short *)``."""
    text = _read_vtm3_c()
    sig = re.search(
        r"void\s+setzeroabc\s*\(\s*"
        r"int\s+f\s*,\s*"
        r"int\s+bw\s*,\s*"
        r"int\s+rnzg\s*,\s*"
        r"short\s*\*\s*sacoef\s*,\s*"
        r"short\s*\*\s*sbcoef\s*,\s*"
        r"short\s*\*\s*sccoef\s*\)",
        text,
    )
    assert sig is not None, "setzeroabc signature does not match expected C declaration"


def test_radius_lookup_step() -> None:
    """Step 1: ``r = radius_table[bw >> 3];``."""
    body = _extract_body()
    assert re.search(r"r\s*=\s*radius_table\s*\[\s*bw\s*>>\s*3\s*\]\s*;", body)


def test_ccoef_formula() -> None:
    """Step 2: ``ccoef = -frac4mul(r, r);``."""
    body = _extract_body()
    assert re.search(r"ccoef\s*=\s*-\s*frac4mul\s*\(\s*r\s*,\s*r\s*\)\s*;", body)


def test_bcoef_formula() -> None:
    """Step 3: ``bcoef = frac4mul(r, cosine_table[f >> 3]);``."""
    body = _extract_body()
    assert re.search(
        r"bcoef\s*=\s*frac4mul\s*\(\s*r\s*,\s*cosine_table\s*\[\s*f\s*>>\s*3\s*\]\s*\)\s*;",
        body,
    )


def test_acoef_formula() -> None:
    """Step 4: ``acoef = 4096 - bcoef - ccoef;``."""
    body = _extract_body()
    assert re.search(r"acoef\s*=\s*4096\s*-\s*bcoef\s*-\s*ccoef\s*;", body)


def test_steps_appear_in_order() -> None:
    """The 4 numerical steps appear top-to-bottom in the C body."""
    body = _extract_body()
    r_pos = body.index("r = radius_table")
    # The C source uses tabs/spaces in front of ccoef etc.; search loosely.
    c_match = re.search(r"ccoef\s*=\s*-\s*frac4mul", body)
    b_match = re.search(r"bcoef\s*=\s*frac4mul", body)
    a_match = re.search(r"acoef\s*=\s*4096", body)
    assert c_match is not None
    assert b_match is not None
    assert a_match is not None
    assert r_pos < c_match.start() < b_match.start() < a_match.start()


def test_antiresonator_output_writes() -> None:
    """The 3 output writes use ``a' = 1/a``, ``b' = -b/a``, ``c' = -c/a`` scaled by ``rnzg``."""
    body = _extract_body()
    # *sacoef = ((4096 * rnzg) / acoef);
    assert re.search(
        r"\*\s*sacoef\s*=\s*\(\s*\(\s*4096\s*\*\s*rnzg\s*\)\s*/\s*acoef\s*\)\s*;",
        body,
    )
    # *sbcoef = -((bcoef * rnzg) / acoef);
    assert re.search(
        r"\*\s*sbcoef\s*=\s*-\s*\(\s*\(\s*bcoef\s*\*\s*rnzg\s*\)\s*/\s*acoef\s*\)\s*;",
        body,
    )
    # *sccoef = -((ccoef * rnzg) / acoef);
    assert re.search(
        r"\*\s*sccoef\s*=\s*-\s*\(\s*\(\s*ccoef\s*\*\s*rnzg\s*\)\s*/\s*acoef\s*\)\s*;",
        body,
    )


# --------------------------------------------------------------------------
# Behavioural pinning.
# --------------------------------------------------------------------------


def _reference(f: int, bw: int, rnzg: int) -> tuple[int, int, int]:
    """Reference implementation of setzeroabc, computed from first principles."""
    r = radius_table[bw >> 3]
    ccoef = -frac4mul(r, r)
    bcoef = frac4mul(r, cosine_table[f >> 3])
    acoef = 4096 - bcoef - ccoef

    def c_div(a: int, b: int) -> int:
        if (a < 0) ^ (b < 0):
            return -(abs(a) // abs(b))
        return abs(a) // abs(b)

    return (
        c_div(4096 * rnzg, acoef),
        -c_div(bcoef * rnzg, acoef),
        -c_div(ccoef * rnzg, acoef),
    )


@pytest.mark.parametrize(
    "f,bw,rnzg,expected",
    [
        # Realistic nasal-zero values (formant frequency in Hz, bw in Hz,
        # gain in Q12). Output values are pinned to the hand-computed
        # reference above to catch regressions in the table imports
        # and frac4mul arithmetic.
        (800, 100, 1024, (4249, -7225, 3999)),
        (2000, 200, 4096, (3147, -1825, 2774)),
        (1000, 50, 2048, (5440, -8667, 5275)),
        (1500, 150, 3000, (3816, -4300, 3484)),
        (400, 60, 2048, (32896, -62596, 31748)),
        (300, 40, 1024, (29746, -57714, 28991)),
    ],
)
def test_python_matches_pinned_reference(
    f: int, bw: int, rnzg: int, expected: tuple[int, int, int]
) -> None:
    """Pinned (f, bw, rnzg) inputs produce the hand-computed coefficients."""
    assert setzeroabc(f, bw, rnzg) == expected


@pytest.mark.parametrize(
    "f,bw,rnzg",
    [
        (800, 100, 1024),
        (2000, 200, 4096),
        (1000, 50, 2048),
        (1500, 150, 3000),
        (400, 60, 2048),
        (300, 40, 1024),
        (3000, 300, 512),
        (250, 80, 2000),
    ],
)
def test_python_matches_reference_implementation(f: int, bw: int, rnzg: int) -> None:
    """The port agrees with the reference implementation for diverse inputs."""
    assert setzeroabc(f, bw, rnzg) == _reference(f, bw, rnzg)


def test_negative_division_uses_truncate_toward_zero() -> None:
    """Negative dividend cases must truncate toward zero (C ``/``), not floor.

    ``ccoef`` is always non-positive (it's ``-r**2``), so ``ccoef * rnzg``
    is non-positive and the division ``ccoef * rnzg / acoef`` has a
    negative dividend whenever ``acoef > 0``. Python's ``//`` would
    floor (round toward negative infinity); the port must round toward
    zero to match C. Negating then gives the slightly larger
    ``sccoef``. The hand-computed expected values above already encode
    this; this test isolates the property explicitly.
    """
    # Pick inputs where the truncate-vs-floor distinction makes a
    # measurable difference. f=800, bw=100, rnzg=1024 gives
    # ccoef = -3855, acoef = 987, so ccoef*rnzg = -3947520. With
    # truncate-toward-zero: -3947520 / 987 = -3999 (then negated -> 3999).
    # With floor: -3947520 // 987 = -4000 (then negated -> 4000).
    f, bw, rnzg = 800, 100, 1024
    _, _, sccoef = setzeroabc(f, bw, rnzg)
    assert sccoef == 3999
    # The naive floor-div implementation would give 4000.
    naive_floor = -((-3855 * rnzg) // 987)
    assert naive_floor == 4000
    assert sccoef != naive_floor


def test_bw_zero_uses_first_radius_entry() -> None:
    """``bw == 0`` indexes ``radius_table[0] == 4096`` (unity radius)."""
    # f=4000 lands well into the cosine table. With r=4096 we get
    # ccoef = -frac4mul(4096, 4096) = -4096 (exactly -1.0 in Q12).
    # bcoef = frac4mul(4096, cosine_table[500]) = frac4mul(4096, 5029) = 5029.
    # acoef = 4096 - 5029 - (-4096) = 3163.
    r = radius_table[0]
    assert r == 4096
    f, bw, rnzg = 4000, 0, 1024
    sacoef, sbcoef, sccoef = setzeroabc(f, bw, rnzg)
    # Check it matches the reference (not a magic-number check -- that's
    # what the parametrised tests are for; here we just want bw=0
    # exercised at all).
    assert (sacoef, sbcoef, sccoef) == _reference(f, bw, rnzg)


def test_f_zero_uses_first_cosine_entry() -> None:
    """``f == 0`` indexes ``cosine_table[0] == 8192`` (cosine at DC)."""
    assert cosine_table[0] == 8192
    # Pick bw=200 so acoef does not collapse to zero. r = radius_table[25] = 3846.
    # ccoef = -frac4mul(3846, 3846) = -(14791716 >> 12) = -(14791716 // 4096) = -3611.
    # Actually 14791716 >> 12 = 3611, so ccoef = -3611. bcoef = frac4mul(3846, 8192) = 7692.
    # acoef = 4096 - 7692 + 3611 = 15.
    f, bw, rnzg = 0, 200, 1024
    assert setzeroabc(f, bw, rnzg) == _reference(f, bw, rnzg)


def test_return_type_is_tuple_of_three_ints() -> None:
    """Return value is a 3-tuple of plain Python ints."""
    result = setzeroabc(800, 100, 1024)
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(isinstance(v, int) for v in result)
