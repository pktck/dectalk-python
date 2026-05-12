"""Verify ``cm_util_string_match`` parity with cm_util.c.

The C function is the case-insensitive unique-prefix matcher used
by the inline-command parser. Tests cover exact match,
case-insensitivity, prefix match, ambiguity, and the empty/null
edge cases.
"""

from __future__ import annotations

import pytest

from dectalk.cmd import string_match as sm

NO = sm.NO_STRING_MATCH


# Mock voice-name table (all lowercase, as the C source expects).
VOICE_NAMES: tuple[bytes, ...] = (
    b"paul",
    b"harry",
    b"betty",
    b"frank",
    b"dennis",
    b"kit",
    b"ursula",
    b"rita",
    b"wendy",
)


def test_exact_match() -> None:
    """Full-match input returns the option's index."""
    assert sm.cm_util_string_match(VOICE_NAMES, b"paul") == 0
    assert sm.cm_util_string_match(VOICE_NAMES, b"wendy") == 8


def test_case_insensitive_exact_match() -> None:
    """Input is case-folded via ls_lower before comparing."""
    assert sm.cm_util_string_match(VOICE_NAMES, b"Paul") == 0
    assert sm.cm_util_string_match(VOICE_NAMES, b"HARRY") == 1
    assert sm.cm_util_string_match(VOICE_NAMES, b"BeTtY") == 2


def test_unique_prefix_match() -> None:
    """A prefix that uniquely identifies one option matches."""
    # 'pau' is a prefix only of 'paul'
    assert sm.cm_util_string_match(VOICE_NAMES, b"pau") == 0
    # 'wen' is unique to 'wendy'
    assert sm.cm_util_string_match(VOICE_NAMES, b"wen") == 8


def test_ambiguous_prefix_returns_no_match() -> None:
    """If multiple options share the prefix, NO_STRING_MATCH."""
    pets = (b"cat", b"car", b"cap")
    # 'ca' is a prefix of all 3 → ambiguous
    assert sm.cm_util_string_match(pets, b"ca") == NO


def test_no_match() -> None:
    """No option starts with the given input."""
    assert sm.cm_util_string_match(VOICE_NAMES, b"zzz") == NO


def test_input_longer_than_option_no_match() -> None:
    """If input is longer than any option, no exact match → NO."""
    assert sm.cm_util_string_match(VOICE_NAMES, b"paulrules") == NO


def test_str_input_accepted() -> None:
    """str input is accepted and Latin-1 encoded."""
    assert sm.cm_util_string_match(VOICE_NAMES, "harry") == 1


def test_empty_string_ambiguous() -> None:
    """Empty string is a prefix of every option → ambiguous → NO."""
    assert sm.cm_util_string_match(VOICE_NAMES, b"") == NO


def test_empty_string_with_one_option_matches() -> None:
    """Empty string against a single option is unambiguous → 0."""
    assert sm.cm_util_string_match((b"only",), b"") == 0


def test_empty_options_returns_no_match() -> None:
    """No options means no match possible."""
    assert sm.cm_util_string_match((), b"paul") == NO


def test_first_match_when_exact_prefix_of_longer() -> None:
    """Exact match short-circuits even if a longer entry also starts with it."""
    options = (b"foo", b"foobar")
    # 'foo' is an exact match for option 0, AND a prefix of option 1.
    # The C source returns immediately on exact match → index 0.
    assert sm.cm_util_string_match(options, b"foo") == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (b"paul", 0),
        (b"HARRY", 1),
        (b"Bet", 2),
        (b"fr", 3),
        (b"de", 4),
        (b"k", 5),
        (b"ur", 6),
        (b"ri", 7),
        (b"wen", 8),
    ],
)
def test_voice_name_unique_prefixes(query: bytes, expected: int) -> None:
    """Each voice name has a unique short prefix."""
    assert sm.cm_util_string_match(VOICE_NAMES, query) == expected
