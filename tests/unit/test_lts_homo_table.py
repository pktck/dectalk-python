"""Verify the homograph rule table matches ls_homo.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts.homo_table import MAX_HOMO_RULE, HomoRule, homo_table

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_homo.h")


def _parse_homo_table() -> tuple[HomoRule, ...]:
    """Return the 27 ``homo_rule`` records from ``ls_homo.h``."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"homo_table\s*\[\s*MAX_HOMO_RULE\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None, "homo_table initialiser not found"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    values = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]+", body)]
    assert len(values) == 4 * MAX_HOMO_RULE
    return tuple(
        HomoRule(values[i], values[i + 1], values[i + 2], values[i + 3])
        for i in range(0, len(values), 4)
    )


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_max_homo_rule_matches() -> None:
    """``MAX_HOMO_RULE`` matches the ``#define`` in ls_homo.h."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(r"#define\s+MAX_HOMO_RULE\s+(\d+)\b", text)
    assert match is not None
    assert int(match.group(1)) == MAX_HOMO_RULE


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_homo_table_matches_c_source() -> None:
    """All 27 entries match ls_homo.h byte-for-byte."""
    c_rules = _parse_homo_table()
    assert c_rules == homo_table


def test_homo_table_length() -> None:
    """``homo_table`` is exactly ``MAX_HOMO_RULE`` long."""
    assert len(homo_table) == MAX_HOMO_RULE


def test_homo_rule_is_frozen() -> None:
    """``HomoRule`` is hashable and immutable (frozen=True, slots=True)."""
    rule = HomoRule(0x80, 0, 0, 0x400)
    assert rule.h_suffix == 0x80
    assert hash(rule) == hash(rule)
    with pytest.raises(AttributeError):
        rule.h_suffix = 1  # type: ignore[misc]


def test_first_rule_ed_suffix() -> None:
    """The first rule strips FC_NOUN from a bare ``-ed`` form."""
    rule = homo_table[0]
    assert rule.h_suffix == 0x80  # FC_ED
    assert rule.h_context == 0
    assert rule.h_select == 0
    assert rule.h_elim == 0x400  # FC_NOUN


def test_second_rule_ed_after_article() -> None:
    """Rule 2: ``-ed`` after an article picks FC_ADJ."""
    rule = homo_table[1]
    assert rule.h_suffix == 0x80  # FC_ED
    assert rule.h_context == 0x4  # FC_ART
    assert rule.h_select == 0x1  # FC_ADJ
    assert rule.h_elim == 0


def test_ing_rules_mirror_ed() -> None:
    """The ``-ing`` rules (2-3) mirror the ``-ed`` rules (0-1)."""
    assert homo_table[2].h_suffix == 0x200  # FC_ING
    assert homo_table[2].h_elim == homo_table[0].h_elim
    assert homo_table[3].h_suffix == 0x200
    assert homo_table[3].h_context == homo_table[1].h_context
    assert homo_table[3].h_select == homo_table[1].h_select
