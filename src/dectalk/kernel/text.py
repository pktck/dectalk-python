"""Text normalization and tokenization for the TTS front end.

This module is the small Python equivalent of the C `KERNEL/usa.c` text
processor. It splits an input string into pronounceable tokens (words,
numbers, punctuation that signals a pause), applying the minimal
normalizations needed for the bundled lexicon:

- Lower / upper case folding (the lexicon stores upper-case).
- Stripping leading/trailing punctuation from each word.
- Sentence-final punctuation (``. ? !``) is reported as a pause token so
  the synthesizer can insert silence.
- Numbers are spoken digit by digit (``2024`` → "two zero two four"); a
  later phase can replace this with a proper number-to-words pass.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Final

from dectalk.kernel.numbers import number_to_words

# Punctuation that ends a sentence and warrants a silence afterwards.
_SENTENCE_PUNCT: Final[frozenset[str]] = frozenset({".", "?", "!"})

# Punctuation that triggers a short pause but isn't sentence-final.
# ruff flags em-dash and en-dash as ambiguous Unicode; we want them here
# because real-world text contains them as clause separators.
_CLAUSE_PUNCT: Final[frozenset[str]] = frozenset(
    {",", ";", ":", "—", "–"}  # noqa: RUF001 - intentional Unicode punctuation
)


class TokenKind(Enum):
    """Categorisation of a normalised token."""

    WORD = "word"
    PAUSE_SHORT = "pause_short"
    PAUSE_LONG = "pause_long"


@dataclass(frozen=True, slots=True)
class Token:
    """One unit produced by :func:`tokenize`.

    Attributes:
        kind: What this token represents.
        text: The normalised text (upper-case for words; empty for pauses).
    """

    kind: TokenKind
    text: str = ""


def tokenize(source: str) -> list[Token]:
    """Split ``source`` into a sequence of :class:`Token` instances.

    Args:
        source: Raw input text.

    Returns:
        Ordered list of tokens. Empty input returns ``[]``.
    """
    raw_tokens = source.split()
    out: list[Token] = []
    for raw in raw_tokens:
        out.extend(_normalize_token(raw))
    return out


def _normalize_token(raw: str) -> Iterable[Token]:
    """Strip surrounding punctuation and emit the appropriate token(s).

    Trailing sentence punctuation produces a long pause; trailing
    clause punctuation produces a short pause. Numeric tokens are spoken
    via :func:`number_to_words`. Hyphenated compounds are split into
    their parts. Currency-prefixed tokens (``$5``) get a "DOLLARS"
    word appended.
    """
    word = raw
    trailing_pause: TokenKind | None = None

    # Strip trailing punctuation, recording the strongest pause class seen.
    while word and not (word[-1].isalnum()):
        last = word[-1]
        if last in _SENTENCE_PUNCT:
            trailing_pause = TokenKind.PAUSE_LONG
        elif last in _CLAUSE_PUNCT and trailing_pause is None:
            trailing_pause = TokenKind.PAUSE_SHORT
        word = word[:-1]

    # Currency: a leading $ before digits.
    currency_suffix = None
    if word.startswith("$") and word[1:].replace(",", "").isdigit():
        currency_suffix = "DOLLARS"
        word = word[1:].replace(",", "")

    # Strip leading punctuation that isn't part of a number.
    while word and not word[0].isalnum():
        word = word[1:]

    # Hyphenated compounds: split and emit each piece in turn. Common in
    # dates ("twenty-four") and noun compounds ("self-driving").
    parts = word.split("-") if "-" in word else [word]

    for part in parts:
        if not part:
            continue
        # Strip stray commas inside large numbers ("1,000").
        if part.replace(",", "").isdigit():
            for w in number_to_words(int(part.replace(",", ""))):
                yield Token(TokenKind.WORD, w)
        else:
            yield Token(TokenKind.WORD, part.upper())

    if currency_suffix is not None:
        yield Token(TokenKind.WORD, currency_suffix)

    if trailing_pause is not None:
        yield Token(trailing_pause)
