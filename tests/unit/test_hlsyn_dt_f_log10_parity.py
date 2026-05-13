"""C-source parity test for ``DT_f_log10`` / ``log10table`` against log10table.c.

Re-parses the C source's ``log10table[]`` literal block plus the
``DT_f_log10`` body and asserts:

- The embedded Python ``log10table`` is the same length and entry-for-
  entry equal to the C array (after the ``f`` suffix strip).
- The Python ``dt_f_log10`` matches the documented branch structure
  (``> 100`` -> math.log10, ``> 10`` -> table+1, else -> table).
- Numerical output across all three branches lines up with
  :func:`math.log10` to a small tolerance, exactly as the C function
  does (modulo float32 round-trips in the C table).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.log10_table import dt_f_log10, log10table

_C_FILE = (
    Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn/log10table.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_c_table() -> tuple[float, ...]:
    """Parse the ``const float log10table[]={...};`` block from log10table.c."""
    text = _read_c()
    match = re.search(
        r"const\s+float\s+log10table\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None, "log10table[] block not found in log10table.c"
    literals = re.findall(r"-?\d+\.\d+f", match.group(1))
    return tuple(float(lit[:-1]) for lit in literals)


def test_log10table_matches_c_source() -> None:
    """Embedded Python ``log10table`` is byte-for-byte equal to the C array."""
    c_table = _extract_c_table()
    assert len(log10table) == len(c_table)
    assert log10table == c_table


def test_log10table_length_is_1001() -> None:
    """The table has 1001 entries (indices 0..1000 inclusive)."""
    assert len(log10table) == 1001


def test_log10table_reference_entries() -> None:
    """Spot-check well-known reference values from the C source."""
    # Index 0 holds the lower-bound placeholder (log10(0.001)).
    assert log10table[0] == -3.0
    # Index 1 = log10(0.01) = -2.0.
    assert log10table[1] == -2.0
    # Index 10 = log10(0.10) = -1.0.
    assert log10table[10] == -1.0
    # Index 100 = log10(1.00) = 0.0.
    assert log10table[100] == 0.0
    # Index 200 = log10(2.00) ~ 0.30103.
    assert log10table[200] == 0.30103
    # Index 1000 = log10(10.0) = 1.0.
    assert log10table[1000] == 1.0


def test_dt_f_log10_signature_in_c_source() -> None:
    """``DT_f_log10`` is defined as ``float DT_f_log10(float input)``."""
    text = _read_c()
    sig = re.search(
        r"float\s+DT_f_log10\s*\(\s*float\s+\w+\s*\)\s*\{",
        text,
    )
    assert sig is not None, "DT_f_log10(float) definition not found in log10table.c"


def test_dt_f_log10_c_branch_structure() -> None:
    """C body contains the expected three-way branch on the input magnitude."""
    text = _read_c()
    match = re.search(
        r"float\s+DT_f_log10\s*\(\s*float\s+\w+\s*\)\s*\{(.+?)\n\}",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    # input > 100 -> math.log10 fall-through.
    assert re.search(r"if\s*\(\s*input\s*>\s*100\.0f\s*\)", body)
    assert re.search(r"return\s*\(\s*float\s*\)\s*\(\s*log10\s*\(\s*input\s*\)\s*\)", body)
    # input > 10 -> pos = input * 10, table[pos] + 1.
    assert re.search(r"if\s*\(\s*input\s*>\s*10\.0f\s*\)", body)
    assert re.search(r"pos\s*=\s*\(\s*int\s*\)\s*\(\s*input\s*\*\s*10\.0f\s*\)", body)
    assert re.search(r"return\s*\(\s*log10table\s*\[\s*pos\s*\]\s*\+\s*1\s*\)", body)
    # Fall-through: pos = input * 100, table[pos].
    assert re.search(r"pos\s*=\s*\(\s*int\s*\)\s*\(\s*input\s*\*\s*100\.0f\s*\)", body)
    assert re.search(r"return\s*\(?\s*log10table\s*\[\s*pos\s*\]\s*\)?", body)


def test_dt_f_log10_reference_inputs_match_math_log10() -> None:
    """``dt_f_log10`` matches ``math.log10`` on a range of representative inputs."""
    # Inputs spanning all three branches: <= 10 (table * 100), 10..100
    # (table * 10), > 100 (math.log10 direct).
    samples = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 9.99, 10.0, 10.5, 25.0, 99.9, 100.0, 100.01]
    for x in samples:
        # The table entries are float32 quantised so we allow a small
        # absolute tolerance. The fall-through > 100 branch should be
        # bit-equal to math.log10 in Python's double precision.
        py = dt_f_log10(x)
        ref = math.log10(x)
        assert math.isclose(py, ref, abs_tol=5e-6), (
            f"dt_f_log10({x}) = {py}, math.log10 = {ref}, delta = {py - ref}"
        )


def test_dt_f_log10_above_100_uses_math_log10_exactly() -> None:
    """Above 100.0 the function bypasses the table entirely."""
    for x in (100.01, 123.456, 1000.0, 9999.0):
        assert dt_f_log10(x) == math.log10(x)


def test_dt_f_log10_at_table_anchors() -> None:
    """Exact table anchors return the embedded float literally."""
    # input=0.01 -> pos=1, table[1] = -2.0.
    assert dt_f_log10(0.01) == log10table[1]
    # input=1.0 -> pos=100, table[100] = 0.0.
    assert dt_f_log10(1.0) == log10table[100]
    # input=10.0 -> pos=1000 (<=10 branch), table[1000] = 1.0.
    assert dt_f_log10(10.0) == log10table[1000]


def test_dt_f_log10_uses_second_branch_above_10() -> None:
    """``10.0 < x <= 100.0`` uses ``table[int(x*10)] + 1``."""
    # input=10.1 -> pos=101, expected = log10table[101] + 1.
    assert dt_f_log10(10.1) == log10table[101] + 1
    # input=50.0 -> pos=500.
    assert dt_f_log10(50.0) == log10table[500] + 1
    # input=99.0 -> pos=990.
    assert dt_f_log10(99.0) == log10table[990] + 1


def test_dt_f_log10_truncation_matches_c_int_cast() -> None:
    """``int(x)`` in Python truncates toward zero just like C's ``(int)``."""
    # 1.99 * 100 = 199.0..., truncates to 199.
    assert dt_f_log10(1.99) == log10table[199]
    # 1.999999 * 100 = 199.999..., still truncates to 199 (not rounds).
    assert dt_f_log10(1.999999) == log10table[199]
