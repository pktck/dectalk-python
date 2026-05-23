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


def test_parse_preserves_form_class_homographs() -> None:
    """Lines with ``WORD|FC`` suffixes split into per-form-class keys.

    Mirrors the ``record,P,...`` / ``record,S,...`` noun/verb minimal
    pair shipped in Dic_us_2002.txt. The bare ``WORD`` key resolves
    to the most-preferred form-class (here ``P``, since there's no
    ``N`` row).
    """
    text = "RECORD|P R EH1 K ER0 D\nRECORD|S R AH0 K OW1 R D\n"
    lex = _parse_lexicon_text(text)
    assert lex["RECORD|P"] == ["R", "EH1", "K", "ER0", "D"]
    assert lex["RECORD|S"] == ["R", "AH0", "K", "OW1", "R", "D"]
    # Bare key defaults to the P (primary / noun) reading when no N
    # entry exists, matching the DECtalk source's preferred default.
    assert lex["RECORD"] == ["R", "EH1", "K", "ER0", "D"]


def test_parse_n_entry_wins_bare_key_over_p_s() -> None:
    """When an ``N`` row coexists with ``P``/``S`` rows, ``N`` wins the bare key."""
    text = (
        "WORD|P P R IH1 M\n"
        "WORD W ER1 D\n"  # the N (default) row
        "WORD|S S EH0 K\n"
    )
    lex = _parse_lexicon_text(text)
    assert lex["WORD"] == ["W", "ER1", "D"]
    assert lex["WORD|P"] == ["P", "R", "IH1", "M"]
    assert lex["WORD|S"] == ["S", "EH0", "K"]


def test_bundled_lexicon_carries_form_class_minimal_pairs() -> None:
    """Re-sourced ``Dic_us_2002.txt`` ships noun/verb minimal pairs.

    Acceptance criterion §2/§4 of issue #128: the bundled artifact
    preserves the source's form-class column so the noun vs verb
    readings of ``record`` (and similar minimal pairs) are
    distinguishable in the loaded lexicon.
    """
    lex = load_builtin_lexicon()
    # The 2002 source carries ``record,P`` (noun, primary stress) and
    # ``record,S`` (verb, secondary stress) as separate entries.
    assert "RECORD|P" in lex, "noun reading of 'record' missing from bundled lexicon"
    assert "RECORD|S" in lex, "verb reading of 'record' missing from bundled lexicon"
    assert lex["RECORD|P"] != lex["RECORD|S"], (
        "noun/verb readings should differ — form-class column was dropped during build"
    )


def test_lookup_form_class_selects_homograph() -> None:
    """``lookup(word, form_class='S')`` returns the verb reading.

    ``form_class='P'`` returns the noun reading. With no
    ``form_class`` argument the default (bare key) is returned —
    which for words present only in P/S form will be the P reading
    (per the preference order ``N > P > S``).
    """
    noun = lookup("record", form_class="P")
    verb = lookup("record", form_class="S")
    assert noun is not None
    assert verb is not None
    assert noun != verb
    # Default returns the noun (P) reading because no N entry exists
    # for 'record' in Dic_us_2002.txt.
    default = lookup("record")
    assert default == noun


def test_lookup_rejects_invalid_form_class() -> None:
    with pytest.raises(ValueError, match="form_class"):
        lookup("hello", form_class="X")


def test_lookup_form_class_returns_none_when_specific_absent() -> None:
    """Asking for a specific FC that isn't present returns ``None``.

    No silent fall-through to a different FC reading.
    """
    # 'hello' only has the default (N) reading.
    assert lookup("hello") is not None
    assert lookup("hello", form_class="P") is None
    assert lookup("hello", form_class="S") is None
