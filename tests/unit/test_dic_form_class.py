"""Verify form_class_strings matches dic_comm.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.dic.form_class import form_class_strings

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/dic/dic_comm.c")


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
def test_form_class_strings_match_c_source() -> None:
    """The 32 entries match the C ``form_class_strings[]`` block."""
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"unsigned\s+char\s*\*\s*form_class_strings\s*\[\s*\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert match is not None
    # Extract quoted strings from the body.
    strings = re.findall(r'"([^"]*)"', match.group(1))
    assert len(strings) == 32
    assert tuple(strings) == form_class_strings


def test_size() -> None:
    """``form_class_strings`` has exactly 32 entries (one per bit)."""
    assert len(form_class_strings) == 32


def test_some_known_entries() -> None:
    """Spot-check a few POS abbreviations at known offsets."""
    assert form_class_strings[0] == " adj"
    assert form_class_strings[10] == " noun"
    assert form_class_strings[17] == " verb"
    assert form_class_strings[31] == " homo"
