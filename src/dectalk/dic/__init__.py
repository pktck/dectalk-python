"""Pronunciation dictionary loader.

Public surface:

- :func:`load_builtin_lexicon` — parse the bundled mini-lexicon (US or UK).
- :func:`load_text_lexicon` — parse an external CMUDict-style file.
- :func:`lookup` — convenience word → phoneme list with the bundled lexicon.
- :func:`set_extra_lexicon` — register an additional lexicon (e.g. CMUDict
  loaded via :func:`load_text_lexicon`) that takes precedence over the
  bundled one.
- :func:`clear_extra_lexicon` — remove a previously-registered extra lexicon.
"""

from pathlib import Path

from dectalk.dic.lexicon import load_builtin_lexicon, load_text_lexicon

__all__ = [
    "clear_extra_lexicon",
    "load_builtin_lexicon",
    "load_text_lexicon",
    "lookup",
    "set_extra_lexicon",
]


# Lazy-cached bundled lexicons keyed by language tag. Each entry is built on
# first lookup and reused thereafter.
_caches: dict[str, dict[str, list[str]]] = {}

# Optional user-supplied lexicon. When set it takes precedence over the
# bundled one — useful for plugging in the full public-domain CMUDict.
_extra_lexicon: dict[str, list[str]] | None = None


def lookup(word: str, *, lang: str = "us") -> list[str] | None:
    """Look up a word in the bundled lexicon (or the registered extra lexicon).

    Args:
        word: Word to look up; case is folded to upper before lookup.
        lang: ``"us"`` (default) or ``"uk"``. Selects which bundled
            lexicon to query when the word isn't in the extra lexicon.

    Returns:
        The word's ARPABET phoneme list, or ``None`` if the word is
        absent from both the extra and the bundled lexicons.

    Raises:
        ValueError: If ``lang`` is not a recognised language tag.
    """
    upper = word.upper()
    if _extra_lexicon is not None and upper in _extra_lexicon:
        return _extra_lexicon[upper]
    if lang not in _caches:
        _caches[lang] = load_builtin_lexicon(lang=lang)
    return _caches[lang].get(upper)


def set_extra_lexicon(lexicon: dict[str, list[str]] | str | Path) -> None:
    """Register an extra lexicon that takes precedence over the bundled one.

    Use this to plug in a larger external dictionary like CMUDict::

        from dectalk.dic import set_extra_lexicon, load_text_lexicon

        set_extra_lexicon(load_text_lexicon("cmudict.dict"))

    Or, equivalently, pass the path directly::

        set_extra_lexicon("cmudict.dict")

    Args:
        lexicon: Either a parsed mapping or a path to a CMUDict-format file.
    """
    global _extra_lexicon  # noqa: PLW0603 - module-level registration, single-process
    _extra_lexicon = lexicon if isinstance(lexicon, dict) else load_text_lexicon(lexicon)


def clear_extra_lexicon() -> None:
    """Remove a previously-registered extra lexicon."""
    global _extra_lexicon  # noqa: PLW0603 - module-level registration, single-process
    _extra_lexicon = None
