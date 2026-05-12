"""Verify the Rule dataclass models par_def.h's rule_struct."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd.rule_struct import PAR_MAX_RULE_LENGTH, Rule

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/par_def.h")


def test_default_construction() -> None:
    """All fields default to zero / empty."""
    r = Rule()
    assert r.special_rule == 0
    assert r.special_value == 0
    assert r.lang_flag == 0
    assert r.mode_flag == 0
    assert r.rule == b""


def test_field_count_matches_c_struct() -> None:
    """The 11 fields match the C ``rule_struct``."""
    fields = Rule.__dataclass_fields__
    expected = {
        "special_rule",
        "special_value",
        "lang_flag",
        "mode_flag",
        "rule_number",
        "next_hit_rule",
        "next_miss_rule",
        "next_goret_hit",
        "next_goret_miss",
        "dict_flag",
        "rule",
    }
    assert set(fields.keys()) == expected
    assert len(fields) == 11


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_par_max_rule_length_matches_c() -> None:
    """``PAR_MAX_RULE_LENGTH`` matches the C value (300)."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    # First non-conditional definition is the canonical one.
    pattern = r"^#define\s+PAR_MAX_RULE_LENGTH\s+(\d+)\b"
    found: list[int] = []
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            found.append(int(match.group(1)))
    # par_def.h has multiple #ifdef'd definitions (300 / 200); 300 is the
    # canonical (non-VOCAL/PARSER_COMPILER) value.
    assert 300 in found
    assert PAR_MAX_RULE_LENGTH == 300


def test_special_rule_tags() -> None:
    """``special_rule`` field accepts 0..4 — the canonical tag values."""
    for tag, _ in enumerate(("normal", "stop", "return", "goto", "goret")):
        r = Rule(special_rule=tag)
        assert r.special_rule == tag


def test_construction_kwargs() -> None:
    """Field values are settable at construction."""
    r = Rule(
        special_rule=3,
        special_value=42,
        rule_number=10,
        next_hit_rule=11,
        next_miss_rule=12,
        rule=b"abc/A/copy",
    )
    assert r.special_rule == 3
    assert r.special_value == 42
    assert r.rule_number == 10
    assert r.rule == b"abc/A/copy"


def test_uses_slots() -> None:
    """Rule uses slots=True."""
    r = Rule()
    assert not hasattr(r, "__dict__")
