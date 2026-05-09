"""Pronunciation dictionary loader.

Public surface:

- :func:`load_builtin_lexicon` — parse the bundled mini-lexicon (US or UK).
- :func:`load_text_lexicon` — parse an external CMUDict-style file.
- :func:`lookup` — convenience word → phoneme list with the bundled lexicon.
"""

from dectalk.dic.lexicon import load_builtin_lexicon, load_text_lexicon

__all__ = ["load_builtin_lexicon", "load_text_lexicon", "lookup"]


# Lazy-cached bundled lexicons keyed by language tag. Each entry is built on
# first lookup and reused thereafter.
_caches: dict[str, dict[str, list[str]]] = {}


def lookup(word: str, *, lang: str = "us") -> list[str] | None:
    """Look up a word in the bundled lexicon.

    Args:
        word: Word to look up; case is folded to upper before lookup.
        lang: ``"us"`` (default) or ``"uk"``. Selects which bundled
            lexicon to query.

    Returns:
        The word's ARPABET phoneme list, or ``None`` if the word is
        absent from the chosen lexicon.

    Raises:
        ValueError: If ``lang`` is not a recognised language tag.
    """
    if lang not in _caches:
        _caches[lang] = load_builtin_lexicon(lang=lang)
    return _caches[lang].get(word.upper())
