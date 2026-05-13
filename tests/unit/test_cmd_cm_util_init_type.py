"""Verify cm_util_init_type matches cmd/cm_util.c."""

from __future__ import annotations

from dectalk.cmd.cm_util_init_type import cm_util_init_type
from dectalk.include.usa_arpa import usa_arpa
from dectalk.include.usa_ascky import usa_ascky
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english, LANG_tables_ready
from dectalk.kernel.language_tables import DtpcLanguageTables


def test_clears_loaded_languages_before_init() -> None:
    """Any prior ``loaded_languages`` chain is dropped before usa_init."""
    state = KsdT()
    state.lang_curr = LANG_english
    state.loaded_languages = DtpcLanguageTables(lang_id=999)
    cm_util_init_type(state)
    # After cleanup + usa_init, the chain head is the brand-new US node.
    assert state.loaded_languages is not None
    assert state.loaded_languages.lang_id == LANG_english


def test_installs_us_english_tables() -> None:
    """After init, the top-level KSD pointers reference the US tables."""
    state = KsdT()
    state.lang_curr = LANG_english
    cm_util_init_type(state)
    assert state.ascky == usa_ascky
    assert state.arpabet == usa_arpa


def test_lang_tables_ready_bit_set() -> None:
    """``lang_ready[LANG_english]`` has ``LANG_tables_ready`` set."""
    state = KsdT()
    state.lang_curr = LANG_english
    cm_util_init_type(state)
    assert state.lang_ready[LANG_english] & LANG_tables_ready


def test_idempotent_replaces_existing_chain() -> None:
    """Calling twice drops the first chain and rebuilds with a fresh node."""
    state = KsdT()
    state.lang_curr = LANG_english
    cm_util_init_type(state)
    first_node = state.loaded_languages
    cm_util_init_type(state)
    second_node = state.loaded_languages
    assert second_node is not None
    assert first_node is not second_node
    # The fresh node should be at the head (chain was cleared first).
    assert second_node.lang_id == LANG_english
