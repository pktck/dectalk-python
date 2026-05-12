"""Verify ``ls_task_find_end_of_word`` + ``wlookup`` parity with ls_task.c."""

from __future__ import annotations

from dectalk.lts import word_scan as ws
from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter


def _word(text: str) -> list[Letter]:
    """Helper: build a LETTER list from a string, EOS-terminated."""
    return [Letter(l_ch=ord(c)) for c in text] + [Letter(l_ch=EOS)]


def test_find_end_of_word_simple() -> None:
    """EOS is at the end of the word."""
    letters = _word("hello")
    assert ws.ls_task_find_end_of_word(letters) == 5


def test_find_end_of_word_starts_at_left() -> None:
    """``left`` shifts the scan start without changing the result."""
    letters = _word("hello")
    # Same end index regardless of starting position.
    assert ws.ls_task_find_end_of_word(letters, left=0) == 5
    assert ws.ls_task_find_end_of_word(letters, left=2) == 5


def test_find_end_of_word_empty() -> None:
    """An empty word: EOS is at index 0."""
    assert ws.ls_task_find_end_of_word([Letter(l_ch=EOS)]) == 0


def test_find_end_of_word_no_eos_returns_length() -> None:
    """If no EOS sentinel, the function returns ``len(letters)``."""
    letters = [Letter(l_ch=ord("x")), Letter(l_ch=ord("y"))]
    assert ws.ls_task_find_end_of_word(letters) == 2


# ---- wlookup ----


def _record(key: str, phonemes: str) -> bytes:
    """Build one ``len, key..., EOS, phonemes...`` record."""
    key_bytes = key.encode("latin-1") + bytes([EOS])
    phon_bytes = phonemes.encode("latin-1") + bytes([0])
    # ``record_len`` in the C source is the byte count of (key + EOS + phonemes
    # + terminator), used to skip the record on mismatch.
    record_body = key_bytes + phon_bytes
    return bytes([len(record_body)]) + record_body


def test_wlookup_finds_exact_match() -> None:
    """An exact (case-folded) match returns the phoneme run."""
    table = _record("the", "DH AX") + bytes([0])  # final 0 terminates table
    word = _word("the")
    result = ws.wlookup(word, table)
    assert result == b"DH AX"


def test_wlookup_case_insensitive() -> None:
    """ls_lower folds upper-case input before comparing."""
    # Key in the table is lowercase 't', 'h', 'e'.
    table = _record("the", "DH AX") + bytes([0])
    upper_word = _word("THE")
    assert ws.wlookup(upper_word, table) == b"DH AX"


def test_wlookup_no_match_returns_none() -> None:
    """No record matches → None."""
    table = _record("the", "DH AX") + bytes([0])
    assert ws.wlookup(_word("xyz"), table) is None


def test_wlookup_walks_multiple_records() -> None:
    """Lookup finds a match past earlier non-matching records."""
    table = _record("a", "AH") + _record("the", "DH AX") + _record("to", "T UW")
    table = table + bytes([0])
    assert ws.wlookup(_word("the"), table) == b"DH AX"
    assert ws.wlookup(_word("to"), table) == b"T UW"
    assert ws.wlookup(_word("a"), table) == b"AH"


def test_wlookup_returns_none_on_empty_table() -> None:
    """Empty table (just the zero terminator) returns None."""
    assert ws.wlookup(_word("the"), bytes([0])) is None
