"""Tests for the bundled lexicon loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from dectalk.dic import lookup
from dectalk.dic.lexicon import _parse_lexicon_text, load_builtin_lexicon, load_text_lexicon


def test_parse_basic_entries() -> None:
    text = "HELLO HH AH0 L OW1\nWORLD W ER1 L D\n"
    lex = _parse_lexicon_text(text)
    assert lex == {
        "HELLO": ["HH", "AH0", "L", "OW1"],
        "WORLD": ["W", "ER1", "L", "D"],
    }


def test_parse_skips_comments_and_blank_lines() -> None:
    text = """
    # this is a comment
    HELLO HH AH0 L OW1

    # another comment
    """
    lex = _parse_lexicon_text(text)
    assert "HELLO" in lex


def test_parse_uppercases_words() -> None:
    text = "hello HH AH0 L OW1\n"
    lex = _parse_lexicon_text(text)
    assert "HELLO" in lex
    assert "hello" not in lex


def test_parse_rejects_word_only_lines() -> None:
    with pytest.raises(ValueError, match="malformed"):
        _parse_lexicon_text("ORPHAN\n")


def test_load_builtin_lexicon_has_demo_words() -> None:
    lex = load_builtin_lexicon()
    for word in ("HELLO", "WORLD", "PYTHON", "DECTALK"):
        assert word in lex, f"expected {word} in bundled lexicon"


def test_load_text_lexicon_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "lex.txt"
    p.write_text("FOO F UW1\nBAR B AA1 R\n", encoding="utf-8")
    lex = load_text_lexicon(p)
    assert lex == {"FOO": ["F", "UW1"], "BAR": ["B", "AA1", "R"]}


def test_lookup_helper_is_case_insensitive() -> None:
    assert lookup("hello") is not None
    assert lookup("HELLO") is not None
    assert lookup("HeLLo") is not None
    assert lookup("xyzzy_not_a_word") is None
