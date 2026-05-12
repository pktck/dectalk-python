"""Verify ``cm_text_get_word`` parity with cm_text.c."""

from __future__ import annotations

import pytest

from dectalk.cmd import text_get_word as tgw

# ---- which=0 (full word extraction) ----


def test_simple_word_which0() -> None:
    """Extract a plain word."""
    assert tgw.cm_text_get_word(b"hello world", 0) == b"hello"


def test_leading_whitespace_skipped() -> None:
    """Leading spaces/tabs/etc. are skipped."""
    assert tgw.cm_text_get_word(b"   hello world", 0) == b"hello"


def test_hyphen_kept_in_word() -> None:
    """``-`` is treated as an in-word character (which=0)."""
    assert tgw.cm_text_get_word(b"twenty-one rest", 0) == b"twenty-one"


def test_period_kept_in_word() -> None:
    """``.`` is treated as an in-word character (which=0)."""
    assert tgw.cm_text_get_word(b"3.14 pi", 0) == b"3.14"


def test_empty_buffer_returns_empty() -> None:
    """An empty buffer returns empty."""
    assert tgw.cm_text_get_word(b"", 0) == b""


def test_only_whitespace_returns_empty() -> None:
    """All-whitespace buffer returns empty."""
    assert tgw.cm_text_get_word(b"   \t  ", 0) == b""


def test_control_byte_82_dropped() -> None:
    """The control byte 0x82 is silently dropped."""
    assert tgw.cm_text_get_word(b"hello\x82world more", 0) == b"helloworld"


def test_punctuation_kept_before_letter() -> None:
    """Punctuation char followed by another in-word char is kept."""
    # "test,test" should be ONE word per BATS #676.
    assert tgw.cm_text_get_word(b"test,test more", 0) == b"test,test"


def test_clause_terminator_ends_word() -> None:
    """A clause-terminating char (e.g. ``?`` ``!``) stops the word."""
    assert tgw.cm_text_get_word(b"hello! world", 0) == b"hello"


# ---- which=1 (abbreviation-lookup mode) ----


def test_abbrev_mode_simple_word() -> None:
    """Extract a plain word in abbrev-lookup mode."""
    assert tgw.cm_text_get_word(b"mr. smith", 1) == b"mr."


def test_abbrev_mode_keeps_hyphen() -> None:
    """``-`` is kept in abbrev mode too."""
    assert tgw.cm_text_get_word(b"foo-bar baz", 1) == b"foo-bar"


def test_abbrev_mode_stops_at_space() -> None:
    """Abbrev mode stops at the first whitespace."""
    assert tgw.cm_text_get_word(b"abc def", 1) == b"abc"


def test_abbrev_mode_keeps_other_punct() -> None:
    """In abbrev mode, ``,`` and ``.`` are kept (only space stops it)."""
    assert tgw.cm_text_get_word(b"a,b,c,d more", 1) == b"a,b,c,d"


# ---- start offset ----


def test_start_offset() -> None:
    """Use ``start`` to extract subsequent words from a clause."""
    buf = b"hello world foo"
    # Words: hello (5), space, world (11), space, foo
    assert tgw.cm_text_get_word(buf, 0, 5) == b"world"


@pytest.mark.parametrize(
    ("text", "which", "expected"),
    [
        (b"AT&T systems", 0, b"AT&T"),
        (b"Mr. Smith arrived", 0, b"Mr."),  # Period kept; capital S of Smith stops next
        (b"3.14159", 0, b"3.14159"),
        (b"3.14159", 1, b"3.14159"),
        (b"hello.\n", 0, b"hello."),  # newline is space-like
        (b"hello,\n", 0, b"hello"),
    ],
)
def test_parametric(text: bytes, which: int, expected: bytes) -> None:
    """Various known cases."""
    assert tgw.cm_text_get_word(text, which) == expected
