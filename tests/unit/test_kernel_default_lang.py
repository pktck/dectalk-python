"""Verify default_lang matches kernel/services.c."""

from __future__ import annotations

from dectalk.kernel.default_lang import default_lang
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_both_ready,
    LANG_english,
    LANG_french,
    LANG_lts_ready,
    LANG_map_ready,
    LANG_none,
    LANG_ph_ready,
)
from dectalk.kernel.language_tables import DtpcLanguageTables


def _english_tables() -> DtpcLanguageTables:
    """Build a small DtpcLanguageTables node for US English."""
    return DtpcLanguageTables(
        link=None,
        lang_id=LANG_english,
        lang_ascky=b"\x01\x02\x03",
        lang_ascky_size=3,
        lang_reverse_ascky=[10, 20, 30],
        lang_arpabet=b"\xaa\xbb",
        lang_arpa_size=2,
        lang_arpa_case=1,
        lang_typing=[b"typing0", b"typing1"],
        lang_error=[b"err0"],
    )


def test_first_ready_signal_sets_flag_but_no_switch() -> None:
    """One ready bit alone doesn't trigger the language switch."""
    state = KsdT()
    default_lang(state, LANG_english, LANG_lts_ready)
    assert state.lang_ready[LANG_english] == LANG_lts_ready
    assert state.lang_curr == LANG_none
    assert state.ascky is None


def test_both_ready_with_no_current_lang_installs_tables() -> None:
    """When all bits ready and lang_curr==LANG_none, language wins."""
    state = KsdT()
    state.loaded_languages = _english_tables()
    default_lang(state, LANG_english, LANG_lts_ready)
    default_lang(state, LANG_english, LANG_ph_ready)
    default_lang(state, LANG_english, LANG_map_ready)
    assert state.lang_ready[LANG_english] == LANG_both_ready
    assert state.lang_curr == LANG_english
    assert state.ascky == b"\x01\x02\x03"
    assert state.ascky_size == 3
    assert state.reverse_ascky == [10, 20, 30]
    assert state.arpabet == b"\xaa\xbb"
    assert state.arpa_size == 2
    assert state.arpa_case == 1
    assert state.typing_table == [b"typing0", b"typing1"]
    assert state.error_table == [b"err0"]


def test_ready_code_zero_forces_switch_even_with_current_lang() -> None:
    """``ready_code == 0`` lets a fully-ready language override lang_curr."""
    state = KsdT()
    state.loaded_languages = _english_tables()
    state.lang_curr = LANG_french  # Pretend FR was selected.
    state.lang_ready[LANG_english] = LANG_both_ready  # Already saturated.
    default_lang(state, LANG_english, 0)
    assert state.lang_curr == LANG_english
    assert state.ascky == b"\x01\x02\x03"


def test_non_zero_ready_code_does_not_steal_lang_curr() -> None:
    """A non-zero ready_code can't override an already-set lang_curr."""
    state = KsdT()
    state.loaded_languages = _english_tables()
    state.lang_curr = LANG_french
    state.lang_ready[LANG_english] = LANG_both_ready & ~LANG_lts_ready
    default_lang(state, LANG_english, LANG_lts_ready)
    assert state.lang_curr == LANG_french
    assert state.ascky is None  # Tables not installed.


def test_pipe_aliases_assigned_on_switch() -> None:
    """``lts_pipe`` / ``ph_pipe`` are aliased to the per-lang pipes."""
    state = KsdT()
    fake_lts_pipe = object()
    fake_ph_pipe = object()
    state.lang_lts[LANG_english] = fake_lts_pipe
    state.lang_ph[LANG_english] = fake_ph_pipe
    state.loaded_languages = _english_tables()
    default_lang(state, LANG_english, LANG_both_ready)
    assert state.lts_pipe is fake_lts_pipe
    assert state.ph_pipe is fake_ph_pipe


def test_walks_loaded_languages_linked_list() -> None:
    """When tables are in a multi-node chain, only the matching node copies."""
    other = DtpcLanguageTables(
        link=None,
        lang_id=LANG_french,
        lang_ascky=b"\xff\xff",
        lang_ascky_size=99,
        lang_arpabet=b"\xcc",
        lang_arpa_size=99,
    )
    english = _english_tables()
    english.link = other
    state = KsdT()
    state.loaded_languages = english
    default_lang(state, LANG_english, LANG_both_ready)
    # English tables are installed; French node's values aren't.
    assert state.ascky == english.lang_ascky
    assert state.ascky_size == english.lang_ascky_size


def test_unmatched_language_leaves_tables_unset() -> None:
    """When ``loaded_languages`` has no matching node, tables stay None."""
    state = KsdT()
    state.loaded_languages = _english_tables()  # English-only chain.
    default_lang(state, LANG_french, LANG_both_ready)
    assert state.lang_curr == LANG_french  # Switch still happens.
    assert state.ascky is None  # But tables stay unset (no FR node).
    assert state.ascky_size == 0


def test_or_accumulates_ready_bits() -> None:
    """Successive ready_codes OR into ``lang_ready[lang]``."""
    state = KsdT()
    default_lang(state, LANG_english, LANG_lts_ready)
    default_lang(state, LANG_english, LANG_ph_ready)
    assert state.lang_ready[LANG_english] == (LANG_lts_ready | LANG_ph_ready)
