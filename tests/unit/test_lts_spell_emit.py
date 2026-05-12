"""Verify ``ls_spel_spell`` parity with ls_spel.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1, WBOUND, USPhoneme
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.spell_emit import ls_spel_spell


def test_single_letter_a_is_stressed_ey() -> None:
    """The letter ``A`` spells out as S1 + EY (stressed)."""
    e = LtsEmitter()
    ls_spel_spell(e, b"A")
    assert e.phones == [S1, int(USPhoneme.EY)]


def test_single_digit_spelled() -> None:
    """A digit spells out using punits — e.g. ``5`` → 'five'."""
    e = LtsEmitter()
    ls_spel_spell(e, b"5")
    assert len(e.phones) > 0


def test_word_wbounds_between_chars() -> None:
    """Multi-char words have WBOUND between each letter."""
    e = LtsEmitter()
    ls_spel_spell(e, b"AB")
    # WBOUND appears between A and B.
    assert WBOUND in e.phones


def test_no_wbound_after_last_char() -> None:
    """The last char doesn't get a trailing WBOUND."""
    e = LtsEmitter()
    ls_spel_spell(e, b"X")
    assert WBOUND not in e.phones


def test_lowercase_a_same_as_uppercase() -> None:
    """``a`` and ``A`` produce identical output (case folded)."""
    e1 = LtsEmitter()
    e2 = LtsEmitter()
    ls_spel_spell(e1, b"a")
    ls_spel_spell(e2, b"A")
    assert e1.phones == e2.phones


def test_empty_word_no_emit() -> None:
    """Empty input emits nothing."""
    e = LtsEmitter()
    ls_spel_spell(e, b"")
    assert e.phones == []


def test_at_amp_t_spelled() -> None:
    """``AT&T`` spells letter-by-letter with the ampersand."""
    e = LtsEmitter()
    ls_spel_spell(e, b"AT&T")
    # Two A-EY (stressed) emissions plus the ampersand and Ts.
    # Just verify the result is non-empty and has multiple WBOUNDs.
    assert e.phones.count(WBOUND) == 3  # between AT&T (4 chars → 3 separators)
