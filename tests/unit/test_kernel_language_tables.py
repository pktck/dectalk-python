"""Verify DtpcLanguageTables / LangTables dataclasses."""

from __future__ import annotations

from dectalk.kernel.language_tables import DtpcLanguageTables, LangTables


def test_dtpc_language_tables_defaults() -> None:
    """All fields default to None / 0."""
    t = DtpcLanguageTables()
    assert t.link is None
    assert t.lang_id == 0
    assert t.lang_ascky is None
    assert t.lang_ascky_size == 0
    assert t.lang_reverse_ascky is None
    assert t.lang_arpabet is None
    assert t.lang_arpa_size == 0
    assert t.lang_arpa_case == 0
    assert t.lang_typing is None
    assert t.lang_error is None


def test_dtpc_language_tables_linked_list() -> None:
    """``link`` lets nodes form a forward-linked list."""
    tail = DtpcLanguageTables(lang_id=2)
    head = DtpcLanguageTables(lang_id=1, link=tail)
    assert head.link is tail
    assert head.link is not None
    assert head.link.lang_id == 2


def test_dtpc_language_tables_with_payload() -> None:
    """A fully-populated US English node."""
    t = DtpcLanguageTables(
        lang_id=0,
        lang_ascky=b"\x01\x02\x03",
        lang_ascky_size=3,
        lang_reverse_ascky=[100, 200, 300],
        lang_arpabet=b"hh ah l ow",
        lang_arpa_size=10,
        lang_arpa_case=0,
    )
    assert t.lang_id == 0
    assert t.lang_ascky_size == 3
    assert t.lang_reverse_ascky == [100, 200, 300]
    assert t.lang_arpabet == b"hh ah l ow"


def test_lang_tables_defaults() -> None:
    """LangTables defaults to all-None."""
    lt = LangTables()
    assert lt.lang_ascky is None
    assert lt.lang_arpa is None
    assert lt.char_map is None
    assert lt.char_types is None
    assert lt.char_lower is None
    assert lt.char_upper is None
    assert lt.char_feat is None
    assert lt.type_table is None
    assert lt.error_table is None


def test_lang_tables_with_payload() -> None:
    """A LangTables can carry actual per-character tables."""
    lt = LangTables(
        char_lower=bytes(range(256)),
        char_upper=bytes(range(256)),
        char_feat=bytes(256),
    )
    assert lt.char_lower is not None
    assert lt.char_lower[ord("A")] == ord("A")
    assert len(lt.char_upper or b"") == 256


def test_both_use_slots() -> None:
    """Both dataclasses use slots=True."""
    assert not hasattr(DtpcLanguageTables(), "__dict__")
    assert not hasattr(LangTables(), "__dict__")
