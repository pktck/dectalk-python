"""Verify the par_def.h rule-engine constants in cmd.rule_states."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import rule_states as rs

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/par_def.h")


def _parse_define(name: str) -> str | None:
    """Return the RHS of a single ``#define <name> <value>`` in par_def.h."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(.+?)\s*(?:/\*.*|//.*)?$"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return match.group(1).strip()
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FAIL", "FAIL", 0),
        ("SUCCESS", "SUCCESS", 1),
        ("OPT_FAIL", "OPT_FAIL", 2),
        ("END_OF_STRING", "END_OF_STRING", 3),
        ("FATAL_FAIL", "FATAL_FAIL", 4),
        ("STOP", "STOP", 5),
    ],
)
def test_rule_return_codes_match_c_source(
    py_attr: str,
    c_name: str,
    expected: int,
) -> None:
    """FAIL / SUCCESS / OPT_FAIL / END_OF_STRING / FATAL_FAIL / STOP."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert int(c_value) == expected
    assert getattr(rs, py_attr) == expected


def test_end_is_slash_paren_null() -> None:
    """End-of-section markers match par_def.h."""
    assert rs.End_Is_Slash == ord("/")
    assert rs.End_Is_Paren == ord(")")
    assert rs.End_Is_Null == 0


def test_return_codes_form_dense_set() -> None:
    """Six return codes 0..5 — dense, no gaps."""
    codes = {
        rs.FAIL,
        rs.SUCCESS,
        rs.OPT_FAIL,
        rs.END_OF_STRING,
        rs.FATAL_FAIL,
        rs.STOP,
    }
    assert codes == {0, 1, 2, 3, 4, 5}
