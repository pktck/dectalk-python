"""Verify usa_init matches kernel/usa.c."""

from __future__ import annotations

from dectalk.include.usa_arpa import usa_arpa
from dectalk.include.usa_ascky import usa_ascky
from dectalk.include.usa_phon_tables import usa_ascky_rev
from dectalk.kernel.default_lang import default_lang
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_english,
    LANG_lts_ready,
    LANG_ph_ready,
    LANG_tables_ready,
)
from dectalk.kernel.language_tables import DtpcLanguageTables
from dectalk.kernel.usa_init import usa_init


def test_appends_node_to_empty_chain() -> None:
    """First call sets loaded_languages to the new node."""
    state = KsdT()
    usa_init(state)
    assert state.loaded_languages is not None
    assert state.loaded_languages.lang_id == LANG_english
    assert state.loaded_languages.link is None


def test_appends_node_to_existing_chain() -> None:
    """When a chain exists, the new node is appended to the tail."""
    state = KsdT()
    existing_head = DtpcLanguageTables(lang_id=42)
    existing_tail = DtpcLanguageTables(lang_id=99)
    existing_head.link = existing_tail
    state.loaded_languages = existing_head
    usa_init(state)
    assert state.loaded_languages is existing_head
    assert existing_head.link is existing_tail
    assert existing_tail.link is not None
    assert existing_tail.link.lang_id == LANG_english


def test_tables_ready_bit_set() -> None:
    """``lang_ready[LANG_english]`` is OR'd with ``LANG_tables_ready``."""
    state = KsdT()
    usa_init(state)
    assert state.lang_ready[LANG_english] == LANG_tables_ready


def test_table_pointers_match_python_sources() -> None:
    """The new node's table fields point at the Python source tables."""
    state = KsdT()
    usa_init(state)
    node = state.loaded_languages
    assert node is not None
    assert node.lang_ascky == usa_ascky
    assert node.lang_ascky_size == len(usa_ascky)
    assert node.lang_reverse_ascky == list(usa_ascky_rev)
    assert node.lang_arpabet == usa_arpa
    assert node.lang_arpa_size == len(usa_arpa)
    assert node.lang_arpa_case == 0


def test_typing_table_has_256_rows() -> None:
    """``lang_typing`` is the 256-entry per-byte pronunciation table."""
    state = KsdT()
    usa_init(state)
    node = state.loaded_languages
    assert node is not None
    assert node.lang_typing is not None
    assert len(node.lang_typing) == 256


def test_default_lang_installs_tables_after_full_ready() -> None:
    """After usa_init + LTS/PH ready signals, the tables are installed."""
    state = KsdT()
    usa_init(state)
    default_lang(state, LANG_english, LANG_lts_ready)
    default_lang(state, LANG_english, LANG_ph_ready)
    assert state.lang_curr == LANG_english
    assert state.arpabet == usa_arpa
    assert state.ascky == usa_ascky
    assert state.ascky_size == len(usa_ascky)
    assert state.arpa_size == len(usa_arpa)


def test_lang_id_is_lang_english() -> None:
    """The new node's ``lang_id`` is :data:`LANG_english`."""
    state = KsdT()
    usa_init(state)
    assert state.loaded_languages is not None
    assert state.loaded_languages.lang_id == LANG_english
