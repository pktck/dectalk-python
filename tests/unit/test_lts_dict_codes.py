"""Verify the dict-context and dict-result constants match ls_dict.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import dict_codes

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_dict.h")
_DEFINE_RE: re.Pattern[str] = re.compile(
    r"^#define\s+([A-Z_][A-Z0-9_]*)\s+(\d+)\b",
)


def _parse_c_defines() -> dict[str, int]:
    """Extract the eight relevant ``#define`` constants from ls_dict.h."""
    keys = {"FIRST", "FABBREV", "SECOND", "SNOPARS", "SINGLE_CHAR", "MISS", "HIT", "ABBREV"}
    out: dict[str, int] = {}
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    for line in text.splitlines():
        match = _DEFINE_RE.match(line)
        if match and match.group(1) in keys:
            out.setdefault(match.group(1), int(match.group(2)))
    return out


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_dict_codes_match_c_source() -> None:
    """All eight constants match the C ``#define`` values byte-for-byte."""
    expected = _parse_c_defines()
    assert expected == {
        "FIRST": 0,
        "FABBREV": 1,
        "SECOND": 2,
        "SNOPARS": 3,
        "SINGLE_CHAR": 4,
        "MISS": 0,
        "HIT": 1,
        "ABBREV": 2,
    }
    for name, value in expected.items():
        assert getattr(dict_codes, name) == value, f"{name} should be {value} per ls_dict.h"


def test_namespace_overlap_intentional() -> None:
    """``MISS=FIRST=0``, ``HIT=FABBREV=1``, ``ABBREV=SECOND=2`` — by design.

    The C source uses two logical namespaces (probe-context vs result)
    that happen to share numeric values. Verifies the Python port
    preserves that overlap rather than silently renumbering one set.
    """
    assert dict_codes.MISS == dict_codes.FIRST == 0
    assert dict_codes.HIT == dict_codes.FABBREV == 1
    assert dict_codes.ABBREV == dict_codes.SECOND == 2


def test_constants_exported() -> None:
    """All eight constants are listed in ``__all__``."""
    assert set(dict_codes.__all__) == {
        "ABBREV",
        "FABBREV",
        "FIRST",
        "HIT",
        "MISS",
        "SECOND",
        "SINGLE_CHAR",
        "SNOPARS",
    }
