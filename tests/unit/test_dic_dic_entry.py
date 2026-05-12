"""Verify DicEntry / DicEntryList dataclasses."""

from __future__ import annotations

from dectalk.dic.dic_entry import DicEntry, DicEntryList


def test_dic_entry_defaults() -> None:
    """DicEntry defaults to (0, b'', b'')."""
    e = DicEntry()
    assert e.fc == 0
    assert e.text == b""
    assert e.phoneme == b""


def test_dic_entry_construction() -> None:
    """DicEntry fields are settable."""
    e = DicEntry(fc=0x80, text=b"hello", phoneme=b"hh ah l ow")
    assert e.fc == 0x80
    assert e.text == b"hello"
    assert e.phoneme == b"hh ah l ow"


def test_dic_entry_list_empty() -> None:
    """A DicEntryList starts empty."""
    lst = DicEntryList()
    assert lst.entries == []
    assert lst.length == 0


def test_dic_entry_list_with_entries() -> None:
    """A DicEntryList reports its length correctly."""
    lst = DicEntryList(
        entries=[
            DicEntry(text=b"alpha"),
            DicEntry(text=b"beta"),
            DicEntry(text=b"gamma"),
        ]
    )
    assert lst.length == 3
    assert lst.entries[1].text == b"beta"


def test_dic_entry_uses_slots() -> None:
    """DicEntry uses slots=True."""
    e = DicEntry()
    assert not hasattr(e, "__dict__")
