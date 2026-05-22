"""C-source parity test for ``par_rule_data`` against ``par_rule2.h``.

Re-parses the C header at test time and asserts the Python module
matches byte-for-byte. The header itself is generated from
``par_rule2.par`` -- the source-of-truth rule description language
for the cmd-stage rule engine.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_rule_data import (
    NUM_RULE_SECTIONS,
    NUM_RULES,
    RULE_DATA_TABLE,
    RULE_INDEX_TABLE,
    RULE_SECTIONS,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_rule2.h"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_header() -> tuple[int, list[int], int, list[int], list[int]]:
    """Re-parse ``par_rule2.h`` and return the five embedded constants."""
    # The header uses CRLF line endings on Linux; read as latin-1 since
    # the rule bytecode is binary-style hex literals interspersed with
    # 8-bit chars in comments.
    text = _C_FILE.read_text(encoding="latin-1").replace("\r\n", "\n")

    m = re.search(r"num_rule_sections\s*=\s*(\d+)\s*;", text)
    assert m is not None, "num_rule_sections missing"
    num_rule_sections = int(m.group(1))

    m = re.search(r"rule_sections\s*\[\s*\d+\s*\]\s*=\s*\{([^}]+)\}\s*;", text)
    assert m is not None, "rule_sections missing"
    rule_sections = [int(x.strip()) for x in m.group(1).replace(",", " ").split() if x.strip()]

    m = re.search(r"num_rules\s*=\s*(\d+)\s*;", text)
    assert m is not None, "num_rules missing"
    num_rules = int(m.group(1))

    m = re.search(r"rule_index_table\s*\[\s*\d+\s*\]\s*=\s*\{([^}]+)\}\s*;", text)
    assert m is not None, "rule_index_table missing"
    rule_index_table: list[int] = []
    for tok in re.split(r"[,\s]+", m.group(1).strip()):
        if tok:
            rule_index_table.append(int(tok, 0))

    m = re.search(r"rule_data_table\s*\[\s*\d+\s*\]\s*=\s*\{(.*?)\}\s*;", text, re.DOTALL)
    assert m is not None, "rule_data_table missing"
    rule_data: list[int] = []
    for tok in re.split(r"[,\s]+", m.group(1).strip()):
        if tok:
            rule_data.append(int(tok, 0))

    return num_rule_sections, rule_sections, num_rules, rule_index_table, rule_data


def test_num_rule_sections_matches_header() -> None:
    """The Python ``NUM_RULE_SECTIONS`` matches the C ``num_rule_sections``."""
    nrs, _, _, _, _ = _parse_header()
    assert nrs == NUM_RULE_SECTIONS


def test_rule_sections_matches_header() -> None:
    """The Python ``RULE_SECTIONS`` matches the C ``rule_sections`` array."""
    _, rs, _, _, _ = _parse_header()
    assert list(RULE_SECTIONS) == rs


def test_num_rules_matches_header() -> None:
    """The Python ``NUM_RULES`` matches the C ``num_rules``."""
    _, _, nr, _, _ = _parse_header()
    assert nr == NUM_RULES


def test_rule_index_table_matches_header() -> None:
    """The Python ``RULE_INDEX_TABLE`` matches the C ``rule_index_table``."""
    _, _, _, rit, _ = _parse_header()
    assert list(RULE_INDEX_TABLE) == rit


def test_rule_data_table_matches_header() -> None:
    """The Python ``RULE_DATA_TABLE`` matches the C ``rule_data_table`` byte-for-byte."""
    _, _, _, _, rdt = _parse_header()
    assert list(RULE_DATA_TABLE) == rdt


def test_index_table_length_equals_num_rules() -> None:
    """Internal consistency: ``RULE_INDEX_TABLE`` length matches ``NUM_RULES``."""
    assert len(RULE_INDEX_TABLE) == NUM_RULES


def test_rule_sections_length_equals_num_rule_sections() -> None:
    """Internal consistency: ``RULE_SECTIONS`` length matches ``NUM_RULE_SECTIONS``."""
    assert len(RULE_SECTIONS) == NUM_RULE_SECTIONS
