"""Verify VersionInfo / LangEntry / LangEnum dataclasses."""

from __future__ import annotations

from dectalk.api.version_info import LangEntry, LangEnum, VersionInfo


def test_version_info_defaults() -> None:
    """VersionInfo defaults to all-zero / empty strings."""
    v = VersionInfo()
    assert v.struct_size == 0
    assert v.struct_version == 0
    assert v.dll_version == 0
    assert v.dtalk_version == 0
    assert v.ver_string == ""
    assert v.language == ""
    assert v.features == 0


def test_version_info_with_us_metadata() -> None:
    """A US-engine version block can be constructed."""
    v = VersionInfo(
        struct_size=64,
        struct_version=0x0001,
        dll_version=1,
        dtalk_version=0x0420,
        ver_string="4.2 CD",
        language="us",
        features=0x000F,
    )
    assert v.dll_version == 1
    assert v.dtalk_version == 0x0420
    assert v.ver_string == "4.2 CD"
    assert v.language == "us"


def test_lang_entry_defaults() -> None:
    """LangEntry defaults to empty strings."""
    le = LangEntry()
    assert le.lang_code == ""
    assert le.lang_name == ""


def test_lang_entry_us() -> None:
    """Constructing a US LangEntry."""
    le = LangEntry(lang_code="us", lang_name="American English")
    assert le.lang_code == "us"
    assert le.lang_name == "American English"


def test_lang_enum_defaults() -> None:
    """LangEnum defaults to (0, False, [])."""
    le = LangEnum()
    assert le.languages == 0
    assert le.multi_lang is False
    assert le.entries == []


def test_lang_enum_with_entries() -> None:
    """LangEnum can hold a list of language entries."""
    le = LangEnum(
        languages=2,
        multi_lang=True,
        entries=[
            LangEntry(lang_code="us", lang_name="American English"),
            LangEntry(lang_code="uk", lang_name="British English"),
        ],
    )
    assert le.languages == 2
    assert le.multi_lang is True
    assert len(le.entries) == 2
    assert le.entries[0].lang_code == "us"
    assert le.entries[1].lang_name == "British English"


def test_all_use_slots() -> None:
    """All three dataclasses use slots=True."""
    assert not hasattr(VersionInfo(), "__dict__")
    assert not hasattr(LangEntry(), "__dict__")
    assert not hasattr(LangEnum(), "__dict__")
