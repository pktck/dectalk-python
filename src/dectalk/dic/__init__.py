"""Pronunciation dictionary loader.

Public surface:

- :func:`load_builtin_lexicon` — parse the bundled mini-lexicon.
- :func:`load_text_lexicon` — parse an external CMUDict-style file.
- :func:`lookup` — convenience word → phoneme list with the bundled lexicon.
"""

from dectalk.dic.lexicon import load_builtin_lexicon, load_text_lexicon

__all__ = ["load_builtin_lexicon", "load_text_lexicon", "lookup"]


# Lazy-cached bundled lexicon. Lookups are case-insensitive on the word.
_cache: dict[str, list[str]] | None = None


def lookup(word: str) -> list[str] | None:
    """Look up a word in the bundled lexicon.

    Args:
        word: Word to look up; case is folded to upper before lookup.

    Returns:
        The word's ARPABET phoneme list, or ``None`` if not in the
        lexicon.
    """
    global _cache  # noqa: PLW0603 - module-level lazy cache, not thread-shared state
    if _cache is None:
        _cache = load_builtin_lexicon()
    return _cache.get(word.upper())
