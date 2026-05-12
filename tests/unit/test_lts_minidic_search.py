"""Verify ``ls_task_minidic_search`` parity with ls_task.c."""

from __future__ import annotations

from dectalk.lts.minidic_search import ls_task_minidic_search
from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter


def _word(text: str) -> list[Letter]:
    """Build an EOS-terminated LETTER list."""
    return [Letter(l_ch=ord(c)) for c in text] + [Letter(l_ch=EOS)]


def test_for_matches() -> None:
    """``for`` matches the first sdic entry."""
    result = ls_task_minidic_search(_word("for"))
    assert result is not None
    # The phoneme run for 'for' is the bytes that follow 'for\0' in sdic.
    # Specifically: 0x78, 0x70, 0x25, 0x0F (terminated by 0x00).
    assert result == bytes([0x78, 0x70, 0x25, 0x0F])


def test_and_matches() -> None:
    """``and`` matches the second sdic entry."""
    result = ls_task_minidic_search(_word("and"))
    assert result is not None
    assert result == bytes([0x78, 0x70, 0x05, 0x20, 0x30])


def test_to_matches() -> None:
    """``to`` matches the 4th sdic entry."""
    result = ls_task_minidic_search(_word("to"))
    assert result is not None
    assert result == bytes([0x78, 0x70, 0x2F, 0x0D])


def test_case_insensitive() -> None:
    """Upper-case input is case-folded via ls_lower."""
    result = ls_task_minidic_search(_word("FOR"))
    assert result is not None
    assert result == bytes([0x78, 0x70, 0x25, 0x0F])


def test_unknown_returns_none() -> None:
    """A word not in sdic returns None."""
    assert ls_task_minidic_search(_word("hello")) is None
    assert ls_task_minidic_search(_word("xyz")) is None
