"""Verify DASH/STAR/HASH/PLUS/EQUAL/NPHONE aliases match ls_defs.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import (
    COMMA,
    HYPHEN,
    MBOUND,
    PERIOD,
    PHO_SYM_TOT,
    SBOUND,
)
from dectalk.lts import rule_phoneme_aliases as rpa

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_defs.h")


def _parse_alias(name: str) -> str | None:
    """Return the right-hand identifier of ``#define <name> (<id>)``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?\s*([A-Z_][A-Z0-9_]*)\s*\)?\s*"
    for raw in text.splitlines():
        line = raw.split("/*")[0].split("//")[0]
        match = re.match(pattern, line)
        if match:
            return match.group(1)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected_target"),
    [
        ("DASH", "DASH", "SBOUND"),
        ("STAR", "STAR", "MBOUND"),
        ("HASH", "HASH", "HYPHEN"),
        ("PLUS", "PLUS", "PERIOD"),
        ("EQUAL", "EQUAL", "COMMA"),
        ("NPHONE", "NPHONE", "PHO_SYM_TOT"),
    ],
)
def test_alias_matches_c(py_attr: str, c_name: str, expected_target: str) -> None:
    """Each alias points at the same C identifier as in ls_defs.h."""
    target = _parse_alias(c_name)
    assert target == expected_target


def test_dash_equals_sbound() -> None:
    """``DASH`` and ``SBOUND`` are the same code."""
    assert rpa.DASH == SBOUND


def test_star_equals_mbound() -> None:
    """``STAR`` and ``MBOUND`` are the same code."""
    assert rpa.STAR == MBOUND


def test_hash_equals_hyphen() -> None:
    """``HASH`` and ``HYPHEN`` are the same code."""
    assert rpa.HASH == HYPHEN


def test_plus_equals_period() -> None:
    """``PLUS`` deliberately re-uses :data:`PERIOD`'s numeric value."""
    assert rpa.PLUS == PERIOD


def test_equal_equals_comma() -> None:
    """``EQUAL`` deliberately re-uses :data:`COMMA`'s numeric value."""
    assert rpa.EQUAL == COMMA


def test_nphone_equals_pho_sym_tot() -> None:
    """``NPHONE`` matches :data:`PHO_SYM_TOT` — the inventory-walk loop limit."""
    assert rpa.NPHONE == PHO_SYM_TOT


def test_no_collisions_among_boundary_aliases() -> None:
    """``DASH``, ``STAR``, ``HASH`` are distinct (no overlap)."""
    assert len({rpa.DASH, rpa.STAR, rpa.HASH}) == 3
