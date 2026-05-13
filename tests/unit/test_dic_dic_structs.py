"""Verify dic.h tool-side dataclasses mirror the C source."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.dic.dic_structs import BIT, C_LEN, P_LEN, S_LEN, Dic, DicObjHeader, Grammar, ItemDsc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/dic/dic.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("S_LEN", "S_LEN", 40),
        ("P_LEN", "P_LEN", 40),
        ("C_LEN", "C_LEN", 80),
    ],
)
def test_length_constants_match_c(py_attr: str, c_name: str, expected: int) -> None:
    """``S_LEN`` / ``P_LEN`` / ``C_LEN`` match dic.h."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(rf"#define\s+{re.escape(c_name)}\s+(\d+)", text)
    assert match is not None
    assert int(match.group(1)) == expected
    if py_attr == "S_LEN":
        assert expected == S_LEN
    elif py_attr == "P_LEN":
        assert expected == P_LEN
    else:
        assert expected == C_LEN


def test_bit_table_dense() -> None:
    """``BIT[i]`` is ``1 << i`` for i in 0..31."""
    assert len(BIT) == 32
    for i in range(32):
        assert BIT[i] == 1 << i


def test_dic_obj_header_defaults() -> None:
    """Default DicObjHeader has zero entries and 500-byte zero dummy."""
    hdr = DicObjHeader()
    assert hdr.no_of_entries == 0
    assert hdr.creation == 0
    assert hdr.modified == 0
    assert hdr.dummy == b"\x00" * 500
    assert len(hdr.dummy) == 500


def test_dic_default_construction() -> None:
    """Default-constructed Dic has empty bytes and 31-entry semantic_class."""
    entry = Dic()
    assert entry.flink is None
    assert entry.spelling == b""
    assert entry.pronunciation == b""
    assert entry.form_class == 0
    assert len(entry.semantic_class) == 31
    assert entry.semantic_class == [0] * 31
    assert entry.frequency == 0
    assert entry.comment == b""


def test_dic_field_assignment() -> None:
    """A Dic entry can be filled with sample data."""
    entry = Dic(
        spelling=b"hello",
        pronunciation=b"hh ax l ow",
        form_class=0x400,
        frequency=1234,
        comment=b"common greeting",
    )
    assert entry.spelling == b"hello"
    assert entry.form_class == 0x400


def test_grammar_default_construction() -> None:
    """Grammar (POS / semantics subset) defaults to zeros."""
    g = Grammar()
    assert g.form_class == 0
    assert len(g.semantic_class) == 31


def test_item_dsc_default_construction() -> None:
    """ItemDsc fields default to zero / empty."""
    item = ItemDsc()
    assert item.buffer_length == 0
    assert item.item_code == 0
    assert item.buffer == []
    assert item.transfer_size == 0


def test_dic_uses_slots() -> None:
    """All four classes are slots-only (no __dict__)."""
    for cls_instance in (ItemDsc(), DicObjHeader(), Dic(), Grammar()):
        assert not hasattr(cls_instance, "__dict__")


def test_dic_forward_link() -> None:
    """Dic.flink can reference another Dic instance."""
    second = Dic(spelling=b"world")
    first = Dic(spelling=b"hello", flink=second)
    assert first.flink is second
    assert first.flink is not None
    assert first.flink.spelling == b"world"
