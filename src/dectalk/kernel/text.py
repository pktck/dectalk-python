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

# Punctuation that ends a sentence and warrants a silence afterwards.
_SENTENCE_PUNCT: Final[frozenset[str]] = frozenset({".", "?", "!"})

# Punctuation that triggers a short pause but isn't sentence-final.
# ruff flags em-dash and en-dash as ambiguous Unicode; we want them here
# because real-world text contains them as clause separators.
_CLAUSE_PUNCT: Final[frozenset[str]] = frozenset(
    {",", ";", ":", "—", "–"}  # noqa: RUF001 - intentional Unicode punctuation
)

# Digit names — used by the digit-by-digit number reader.
_DIGIT_WORDS: Final[dict[str, str]] = {
    "0": "ZERO",
    "1": "ONE",
    "2": "TWO",
    "3": "THREE",
    "4": "FOUR",
    "5": "FIVE",
    "6": "SIX",
    "7": "SEVEN",
    "8": "EIGHT",
    "9": "NINE",
}


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
    clause punctuation produces a short pause. Numeric tokens are read
    digit-by-digit until the prosody/normalisation pass can handle them
    properly.
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

    # Strip leading punctuation; we don't track these as separate tokens
    # because the bundled lexicon doesn't pronounce them.
    while word and not word[0].isalnum():
        word = word[1:]

    if word:
        if word.isdigit():
            for d in word:
                yield Token(TokenKind.WORD, _DIGIT_WORDS[d])
        else:
            yield Token(TokenKind.WORD, word.upper())

    if trailing_pause is not None:
        yield Token(trailing_pause)
