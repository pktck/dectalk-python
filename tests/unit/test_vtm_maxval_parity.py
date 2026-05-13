"""C-source parity test for ``getmax`` / ``checkmax`` against vtm3.c.

Re-parses the inline-helper bodies from
``src/dapi/src/vtm/vtm3.c`` and asserts the absolute-value
folding pattern + comparison shape match the Python ports.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.maxval import checkmax, getmax

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtm3.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtm3_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(func: str) -> str:
    text = _read_vtm3_c()
    match = re.search(
        rf"_inline\s+(?:void|int)\s+{re.escape(func)}\s*\([^)]*\)\s*"
        rf"(?://[^\n]*\n\s*)?\{{(.+?)^\}}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{func}() definition not found in vtm3.c"
    return match.group(1)


def test_getmax_signature_matches_c() -> None:
    """C signature: ``_inline void getmax(S32 value, S32 *maxval)``."""
    text = _read_vtm3_c()
    sig = re.search(
        r"_inline\s+void\s+getmax\s*\(\s*S32\s+\w+\s*,\s*S32\s*\*\s*\w+\s*\)",
        text,
    )
    assert sig is not None


def test_getmax_absolute_value_fold() -> None:
    """getmax body: ``if (value < 0) value = -value;``."""
    body = _extract_body("getmax")
    assert re.search(r"if\s*\(\s*value\s*<\s*0\s*\)", body)
    assert re.search(r"value\s*=\s*-\s*value\s*;", body)


def test_getmax_max_update() -> None:
    """getmax body: ``if (value > *maxval) *maxval = value;``."""
    body = _extract_body("getmax")
    assert re.search(r"if\s*\(\s*value\s*>\s*\*\s*maxval\s*\)", body)
    assert re.search(r"\*\s*maxval\s*=\s*value\s*;", body)


def test_checkmax_signature_matches_c() -> None:
    """C signature: ``_inline int checkmax(S32 value, S32 checkval)``."""
    text = _read_vtm3_c()
    sig = re.search(
        r"_inline\s+int\s+checkmax\s*\(\s*S32\s+\w+\s*,\s*S32\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_checkmax_or_predicate() -> None:
    """checkmax body: ``value > checkval || value < (-checkval)``."""
    body = _extract_body("checkmax")
    assert re.search(
        r"if\s*\(\s*value\s*>\s*checkval\s*\|\|\s*value\s*<\s*\(\s*-\s*checkval\s*\)\s*\)",
        body,
    )


def test_python_getmax_tracks_positive() -> None:
    """Positive value larger than current max updates the tracker."""
    tracker = [10]
    getmax(50, tracker)
    assert tracker[0] == 50


def test_python_getmax_folds_negative_to_abs() -> None:
    """``getmax(-100, [10])`` updates to 100 (abs)."""
    tracker = [10]
    getmax(-100, tracker)
    assert tracker[0] == 100


def test_python_getmax_no_update_when_smaller() -> None:
    """Value smaller than current max leaves tracker unchanged."""
    tracker = [100]
    getmax(50, tracker)
    assert tracker[0] == 100


def test_python_getmax_no_update_on_negative_smaller_abs() -> None:
    """``|value|`` smaller than tracker is no-op."""
    tracker = [100]
    getmax(-50, tracker)
    assert tracker[0] == 100


def test_python_getmax_equal_no_update() -> None:
    """Equal magnitude is no-op (strict `>` predicate)."""
    tracker = [100]
    getmax(100, tracker)
    assert tracker[0] == 100


def test_python_checkmax_returns_1_when_exceeds() -> None:
    """``|value| > checkval`` => 1."""
    assert checkmax(50, 10) == 1
    assert checkmax(-50, 10) == 1


def test_python_checkmax_returns_0_when_within() -> None:
    """``|value| <= checkval`` => 0."""
    assert checkmax(10, 10) == 0
    assert checkmax(-10, 10) == 0
    assert checkmax(0, 10) == 0


def test_python_checkmax_returns_1_when_negative_exceeds() -> None:
    """``value < -checkval`` triggers the second OR branch."""
    assert checkmax(-100, 50) == 1
