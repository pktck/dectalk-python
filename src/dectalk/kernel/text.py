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

from dectalk.kernel.normalize import try_date, try_phone, try_url
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
    clause punctuation produces a short pause. Recognised date / phone
    / URL patterns are routed through :mod:`dectalk.kernel.normalize`;
    numeric tokens are spoken via :func:`number_to_words`; hyphenated
    compounds are split into their parts. Currency-prefixed tokens
    (``$5``) get a "DOLLARS" word appended.
    """
    # URLs are matched on the raw token: ``://`` and ``.`` are part of
    # their syntax and must not be stripped first.
    url_words = try_url(raw)
    if url_words is not None:
        for w in url_words:
            yield Token(TokenKind.WORD, w)
        return

    word, trailing_pause, trailing_punct = _strip_trailing_punct(raw)

    currency_suffix: str | None = None
    if word.startswith("$") and word[1:].replace(",", "").isdigit():
        currency_suffix = "DOLLARS"
        word = word[1:].replace(",", "")

    while word and not word[0].isalnum():
        word = word[1:]

    body = list(_body_words(word))

    for w in body:
        yield Token(TokenKind.WORD, w)
    if currency_suffix is not None:
        yield Token(TokenKind.WORD, currency_suffix)
    if trailing_pause is not None:
        yield Token(trailing_pause, trailing_punct)


def _strip_trailing_punct(raw: str) -> tuple[str, TokenKind | None, str]:
    """Strip trailing punctuation; return the strongest pause class seen.

    Returns a (stripped_word, pause_kind, pause_char) tuple. ``pause_char``
    is the actual punctuation character that triggered the strongest pause
    (``.`` / ``!`` / ``?`` for long, ``,`` / ``;`` / ``:`` for short) so
    downstream encoders can map it to DECtalk's prosodic markers.
    """
    word = raw
    pause: TokenKind | None = None
    pause_char: str = ""
    while word and not word[-1].isalnum():
        last = word[-1]
        if last in _SENTENCE_PUNCT:
            pause = TokenKind.PAUSE_LONG
            pause_char = last
        elif last in _CLAUSE_PUNCT and pause is None:
            pause = TokenKind.PAUSE_SHORT
            pause_char = last
        word = word[:-1]
    return word, pause, pause_char


def _body_words(word: str) -> Iterable[str]:
    """Expand the inner-word body into spoken word tokens."""
    if not word:
        return

    # Date / phone matchers swallow the whole token if they fire.
    for matcher in (try_date, try_phone):
        matched = matcher(word)
        if matched is not None:
            yield from matched
            return

    # Hyphen splitting: "self-driving" -> SELF DRIVING, "twenty-four" -> ...
    parts = word.split("-") if "-" in word else [word]
    for part in parts:
        if not part:
            continue
        if part.replace(",", "").isdigit():
            yield from number_to_words(int(part.replace(",", "")))
        else:
            yield part.upper()
