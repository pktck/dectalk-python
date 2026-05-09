"""Lexicon (word → ARPABET phonemes) loader.

Loads ``src/dectalk/data/lexicon_us.txt`` — a small bundled word list
covering common English vocabulary. The full DECtalk Dic_us.txt is
proprietary FONIX and cannot be redistributed; users wanting full
coverage can wire up CMUDict (public domain) via this module's
:func:`load_text_lexicon` helper.

Format: one entry per line, ``WORD whitespace ARPABET-PHONEMES``. Lines
beginning with ``#`` are comments. Blank lines are skipped.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Final

# The bundled lexicon resources within the dectalk.data package.
_BUILTIN_LEXICON_RESOURCE: Final[str] = "lexicon_us.txt"
_UK_OVERRIDE_RESOURCE: Final[str] = "lexicon_uk.txt"


def load_text_lexicon(path: str | Path) -> dict[str, list[str]]:
    """Parse a CMUDict-style text lexicon.

    Args:
        path: Path to a text file with one ``WORD PHONEME PHONEME ...``
            entry per line. Comments start with ``#``; blank lines skipped.

    Returns:
        Mapping from upper-cased word to its phoneme list.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If a non-comment line has fewer than 2 whitespace-
            separated tokens (a word and at least one phoneme).
    """
    text = Path(path).read_text(encoding="utf-8")
    return _parse_lexicon_text(text)


def load_builtin_lexicon(*, lang: str = "us") -> dict[str, list[str]]:
    """Parse the bundled mini-lexicon shipped with the dectalk package.

    Args:
        lang: ``"us"`` (default) returns the US lexicon. ``"uk"`` layers
            British-English overrides on top of the US base.

    Returns:
        Mapping from upper-cased word to its phoneme list. The returned
        dict is freshly built each call so callers can mutate it freely.

    Raises:
        ValueError: If ``lang`` is not a recognised language tag.
    """
    base_text = (
        resources.files("dectalk.data")
        .joinpath(_BUILTIN_LEXICON_RESOURCE)
        .read_text(encoding="utf-8")
    )
    lex = _parse_lexicon_text(base_text)
    if lang == "us":
        return lex
    if lang == "uk":
        uk_text = (
            resources.files("dectalk.data")
            .joinpath(_UK_OVERRIDE_RESOURCE)
            .read_text(encoding="utf-8")
        )
        lex.update(_parse_lexicon_text(uk_text))
        return lex
    raise ValueError(f"unknown lang {lang!r}; supported values: 'us', 'uk'")


def _parse_lexicon_text(text: str) -> dict[str, list[str]]:
    """Internal parser; public callers should use the loaders above."""
    lex: dict[str, list[str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        min_tokens = 2  # word + at least one phoneme
        if len(parts) < min_tokens:
            raise ValueError(f"malformed lexicon line: {raw_line!r}")
        word = parts[0].upper()
        phonemes = parts[1:]
        lex[word] = phonemes
    return lex
