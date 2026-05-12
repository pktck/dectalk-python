"""Verify ``SuffRule`` dataclass mirrors ls_dict.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts.suff_rule import SUFF_RULE_TEXT_MAX, SuffRule

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_dict.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_suff_rule_struct_definition() -> None:
    """C ``struct suff_rule`` field set matches the Python dataclass."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"struct\s+suff_rule\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    c_fields = {
        name.strip().rstrip(";")
        for name in re.findall(
            r"^\s*(?:U32|unsigned\s+char|S32|short|int|char)\s+(\w+)",
            body,
            re.MULTILINE,
        )
    }
    py_fields = set(SuffRule.__slots__)
    assert c_fields == py_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_suff_rule_text_max() -> None:
    """``rule[256]`` — the byte buffer length matches the C constant 256."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(r"rule\s*\[\s*(\d+)\s*\]", text)
    assert match is not None
    assert int(match.group(1)) == SUFF_RULE_TEXT_MAX


def test_default_construction() -> None:
    """All fields default to zero / empty bytes."""
    rule = SuffRule()
    assert rule.next == 0
    assert rule.fc == 0
    assert rule.rule == b""


def test_field_assignment() -> None:
    """Field assignment works for all named attributes."""
    rule = SuffRule(next=42, fc=0x400, rule=b"\x00ing")
    assert rule.next == 42
    assert rule.fc == 0x400
    assert rule.rule == b"\x00ing"


def test_uses_slots() -> None:
    """``SuffRule`` is a slots dataclass — no __dict__."""
    rule = SuffRule()
    assert not hasattr(rule, "__dict__")


def test_text_max_constant() -> None:
    """``SUFF_RULE_TEXT_MAX`` is 256 bytes."""
    assert SUFF_RULE_TEXT_MAX == 256
