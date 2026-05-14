"""Specialised text-normalization rules for dates, phone numbers, URLs.

The base tokenizer in :mod:`dectalk.kernel.text` handles plain words,
numbers, currency, and hyphenated compounds. This module adds a few
extra patterns that benefit from dedicated handling:

- **Dates**: ``2024-05-09``, ``05/09/2024``, ``2024/05/09`` — read out
  with a "slash"/"dash" connector when ambiguous, or as month-day-year
  for ISO format.
- **Phone numbers**: ``555-1212``, ``(555) 555-1212``,
  ``+1-555-555-1212`` — read digit by digit grouped by visual chunks.
- **URLs**: ``https://example.com/path`` — read scheme + host + path,
  spelling out the domain and reading the path digit by digit / letter
  by letter (we don't have a great solution for arbitrary text in
  paths but at least we recognise and pronounce the structure).

Each function returns a list of upper-case word tokens; the tokenizer
calls them when its pattern matchers fire.
"""

from __future__ import annotations

import re
from typing import Final

from dectalk.kernel.numbers import number_to_words

# ISO-style date: 4-digit year - 2-digit month - 2-digit day, with - or / separator.
_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")

# US-style date: month/day/year or month-day-year. Year is 2 or 4 digits.
_US_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2}|\d{4})$")

# Phone number patterns. We accept several common forms and normalise to
# digit-by-digit reading with sensible visual grouping.
_PHONE_RES: Final[tuple[re.Pattern[str], ...]] = (
    # Phone-number patterns require at least one visual separator
    # (space/dot/dash/parens). A raw digit string ("1234567890") is
    # NOT a phone number -- DECtalk's number-expansion path treats it
    # as a multi-digit integer ("one billion two hundred..."). The
    # pre-fix behaviour misclassified bare 10-digit strings as phones.
    re.compile(r"^\+?(\d{1,3})[\s.-]\(?(\d{3})\)?[\s.-](\d{3})[\s.-](\d{4})$"),
    re.compile(r"^\(?(\d{3})\)\s?(\d{3})[\s.-]?(\d{4})$"),
    re.compile(r"^(\d{3})[\s.-](\d{3})[\s.-](\d{4})$"),
    re.compile(r"^(\d{3})[\s.-](\d{4})$"),
)

# URL pattern (very loose — matches scheme + authority).
_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"^(https?|ftp)://([^/\s]+)(/\S*)?$",
    re.IGNORECASE,
)

# Maximum month / day values used by date-pattern sanity checks.
_MAX_MONTH: Final[int] = 12
_MAX_DAY: Final[int] = 31
# Year cutoff for two-digit years: <= this is interpreted as 2000+, otherwise 1900+.
_TWO_DIGIT_YEAR_PIVOT: Final[int] = 50
_TWO_DIGIT_YEAR_LEN: Final[int] = 2

_MONTH_NAMES: Final[tuple[str, ...]] = (
    "JANUARY", "FEBRUARY", "MARCH", "APRIL",
    "MAY", "JUNE", "JULY", "AUGUST",
    "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
)  # fmt: skip

_DIGIT_NAMES: Final[tuple[str, ...]] = (
    "ZERO", "ONE", "TWO", "THREE", "FOUR",
    "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
)  # fmt: skip


def try_date(token: str) -> list[str] | None:
    """If ``token`` looks like a date, return its spoken-word expansion.

    Recognises ISO (``2024-05-09``) and US (``5/9/2024``, ``05-09-24``)
    layouts. Returns None for anything else so the caller can fall
    through to plain numeric handling.

    Args:
        token: Single whitespace-stripped token.

    Returns:
        Word list (e.g. ``["MAY", "NINTH", ...]``) or None.
    """
    m = _ISO_DATE_RE.match(token)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _date_words(year, month, day)
    m = _US_DATE_RE.match(token)
    if m:
        month, day, year_str = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(year_str)
        # Two-digit year disambiguation: 00-49 -> 2000s, 50-99 -> 1900s.
        if len(year_str) == _TWO_DIGIT_YEAR_LEN:
            year += 2000 if year < _TWO_DIGIT_YEAR_PIVOT else 1900
        return _date_words(year, month, day)
    return None


def _date_words(year: int, month: int, day: int) -> list[str] | None:
    """Spell a (year, month, day) triple, or None if numbers aren't sane."""
    if not (1 <= month <= _MAX_MONTH and 1 <= day <= _MAX_DAY):
        return None
    out = [_MONTH_NAMES[month - 1]]
    out.extend(number_to_words(day))
    out.extend(number_to_words(year))
    return out


def try_phone(token: str) -> list[str] | None:
    """If ``token`` looks like a phone number, return digit-by-digit reading."""
    for pattern in _PHONE_RES:
        m = pattern.match(token)
        if m:
            chunks = [_digits(g) for g in m.groups()]
            # Insert a short pause word between visual groups by joining
            # with a sentinel that the synthesiser maps to a brief silence.
            return [w for chunk in chunks for w in chunk]
    return None


def _digits(text: str) -> list[str]:
    """Read a digit string letter by letter (``"555"`` -> FIVE FIVE FIVE)."""
    return [_DIGIT_NAMES[int(c)] for c in text if c.isdigit()]


def try_url(token: str) -> list[str] | None:
    """If ``token`` looks like a URL, return a spoken-word expansion."""
    m = _URL_RE.match(token)
    if m is None:
        return None
    scheme, host, path = m.group(1).lower(), m.group(2), m.group(3) or ""
    out: list[str] = []
    out.extend(_spell_letters(scheme))
    out.append("COLON")
    out.append("SLASH")
    out.append("SLASH")
    # Spell the host with "dot" between labels.
    labels = host.split(".")
    for i, label in enumerate(labels):
        if i > 0:
            out.append("DOT")
        # Keep recognisable words; spell anything weird.
        if label.isalpha():
            out.append(label.upper())
        else:
            out.extend(_spell_letters(label))
    if path:
        out.append("SLASH")
        for chunk in path.lstrip("/").split("/"):
            if chunk:
                out.extend(_spell_letters(chunk))
                out.append("SLASH")
        if out[-1] == "SLASH":
            out.pop()
    return out


def _spell_letters(text: str) -> list[str]:
    """Spell each character of ``text`` (digits as words, letters upper-cased)."""
    out: list[str] = []
    for c in text:
        if c.isdigit():
            out.append(_DIGIT_NAMES[int(c)])
        elif c.isalpha():
            out.append(c.upper())
    return out
