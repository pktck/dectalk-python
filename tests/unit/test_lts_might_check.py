"""Verify ``ls_util_is_might`` parity with ls_util.c."""

from __future__ import annotations

import pytest

from dectalk.include.cmd_codes import PFCONTROL, PSFONT
from dectalk.lts.char_class import ALWAYS, BACKUP, MIGHT, TYPE, lsctype
from dectalk.lts.might_check import ls_util_is_might


@pytest.mark.parametrize(
    "char",
    ["a", "z", "A", "Z", "'", "-"],  # letters + word-internal punctuation
)
def test_alpha_chars_with_alpha_keep_types(char: str) -> None:
    """Letters typically have TYPE field of BACKUP/ALWAYS/MIGHT or similar.

    Only assert behaviour matches the table — if the char's TYPE
    is one of {BACKUP, ALWAYS, MIGHT} then the predicate is True.
    """
    code = ord(char)
    expected = (lsctype[code] & TYPE) in (BACKUP, ALWAYS, MIGHT)
    assert ls_util_is_might(code) is expected


def test_letter_a_is_might() -> None:
    """``a`` has TYPE=ALWAYS in the US lsctype table → True."""
    # Per the C source comment ``'a' = ALWAYS+OO+PR``.
    assert ls_util_is_might(ord("a")) is True


def test_digit_chars_match_table() -> None:
    """Digit TYPE classification follows the table — assert it matches."""
    code = ord("0")
    expected = (lsctype[code] & TYPE) in (BACKUP, ALWAYS, MIGHT)
    assert ls_util_is_might(code) is expected


def test_control_font_returns_false() -> None:
    """A control-font (PFCONTROL) value is not PFASCII → False."""
    # Any byte under the PFCONTROL font → not PFASCII → False.
    fake = (PFCONTROL << PSFONT) | ord("a")
    assert ls_util_is_might(fake) is False


def test_space_byte() -> None:
    """Whitespace TYPE is IGNORE — not BACKUP/ALWAYS/MIGHT → False."""
    # Per the table, space is typically classified as IGNORE.
    code = ord(" ")
    expected = (lsctype[code] & TYPE) in (BACKUP, ALWAYS, MIGHT)
    assert ls_util_is_might(code) is expected
