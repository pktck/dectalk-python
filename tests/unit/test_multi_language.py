"""Tests for the multi-language lexicon and phoneme conversion."""

from __future__ import annotations

import pytest

from dectalk.dic import lookup
from dectalk.dic.dectalk_phonemes_multi import decode_lang


def test_decode_lang_supports_all_six_languages() -> None:
    """All canonical DECtalk language tags should accept input without raising."""
    for lang in ("us", "uk", "fr", "de", "sp", "la"):
        assert decode_lang("k@t", lang=lang) == ["K", "AE0", "T"]


def test_decode_lang_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown lang"):
        decode_lang("k@t", lang="xx")


def test_spanish_overrides_apply() -> None:
    """Castilian /θ/ uses TH; LA replaces it with S (seseo)."""
    sp = decode_lang("'aTo", lang="sp")  # something like /áθo/
    la = decode_lang("'aTo", lang="la")
    assert "TH" in sp
    assert "S" in la
    assert "TH" not in la


def test_spanish_handles_palatal_n() -> None:
    """Spanish ñ (DECtalk N) should produce N + Y."""
    out = decode_lang("a'No", lang="sp")
    assert out == ["AA0", "N", "Y", "OW1"]


def test_french_handles_accented_vowels() -> None:
    """French é, è, ê are mapped to ARPABET vowel approximations."""
    out_e = decode_lang("é", lang="fr")
    out_eg = decode_lang("è", lang="fr")
    assert out_e == ["EY0"]
    assert out_eg == ["EH0"]


def test_german_handles_ts_affricate() -> None:
    """German T is /ts/ (the spelling 'z')."""
    out = decode_lang("Ta", lang="de")
    assert out == ["T", "S", "AA0"]


@pytest.mark.parametrize("lang", ["us", "uk", "fr", "de", "sp", "la"])
def test_lookup_supports_all_languages(lang: str) -> None:
    """Each language's bundled lexicon should at least load without error."""
    # The actual word lookup may return None — DECtalk's German dictionary
    # only has ~9 entries, etc. We just need the loader path to succeed.
    result = lookup("hello", lang=lang)
    assert result is None or isinstance(result, list)


def test_french_dictionary_has_entries() -> None:
    from dectalk.dic.lexicon import load_builtin_lexicon  # noqa: PLC0415

    lex = load_builtin_lexicon(lang="fr")
    assert len(lex) >= 100, f"expected >=100 French entries, got {len(lex)}"


def test_spanish_dictionary_has_entries() -> None:
    from dectalk.dic.lexicon import load_builtin_lexicon  # noqa: PLC0415

    lex = load_builtin_lexicon(lang="sp")
    assert len(lex) >= 100
