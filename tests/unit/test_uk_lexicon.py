"""Tests for the UK English lexicon overrides."""

from __future__ import annotations

import pytest

from dectalk.api import speak, text_to_phonemes
from dectalk.dic import lookup
from dectalk.dic.lexicon import load_builtin_lexicon


def test_uk_lexicon_loads() -> None:
    lex = load_builtin_lexicon(lang="uk")
    assert "WORLD" in lex
    assert "COLOUR" in lex


def test_uk_overrides_us_for_shared_words() -> None:
    """Tomato is the canonical US/UK pronunciation difference."""
    us = lookup("tomato", lang="us")
    uk = lookup("tomato", lang="uk")
    assert us is not None
    assert uk is not None
    assert us != uk


def test_uk_specific_word_unknown_in_us() -> None:
    """COLOUR appears in the UK overrides but not in the US base lexicon."""
    assert lookup("colour", lang="us") is None
    assert lookup("colour", lang="uk") is not None


def test_speak_lang_passes_through() -> None:
    """speak(lang="uk") should produce different phonemes than the default."""
    us_phones = text_to_phonemes("water letter", lang="us")
    uk_phones = text_to_phonemes("water letter", lang="uk")
    assert us_phones != uk_phones


def test_unknown_lang_raises() -> None:
    with pytest.raises(ValueError, match="unknown lang"):
        load_builtin_lexicon(lang="zz")


def test_speak_uk_produces_audio() -> None:
    samples = speak("hello world", lang="uk")
    assert samples.size > 0
