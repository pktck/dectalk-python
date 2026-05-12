"""Verify versdef.h version fragments."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include import versdef as vd

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/versdef.h")


def _parse_define(name: str) -> str | None:
    """Return the quoted string value of ``#define <name> "..."``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf'^#define\s+{re.escape(name)}\s+"([^"]*)"'
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return match.group(1)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("REVMAJOR", "REVMAJOR", "4"),
        ("REVMINOR", "REVMINOR", "4"),
        ("REVTYPE", "REVTYPE", "A"),
        ("REVNO", "REVNO", "A"),
    ],
)
def test_versdef_matches_c(py_attr: str, c_name: str, expected: str) -> None:
    """Each version fragment matches versdef.h."""
    c_value = _parse_define(c_name)
    assert c_value == expected
    assert getattr(vd, py_attr) == expected


def test_concatenated_version_string() -> None:
    """Concatenated version string is ``"4.4A"``."""
    assert f"{vd.REVMAJOR}.{vd.REVMINOR}{vd.REVTYPE}" == "4.4A"


def test_revtype_and_revno_letter_only() -> None:
    """Both REVTYPE and REVNO are single uppercase letters."""
    assert len(vd.REVTYPE) == 1
    assert vd.REVTYPE.isupper()
    assert len(vd.REVNO) == 1
    assert vd.REVNO.isupper()
