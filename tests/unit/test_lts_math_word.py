"""Verify ``ls_task_math_mode`` parity with ls_task.c."""

from __future__ import annotations

from dectalk.lts.math_word import ls_task_math_mode


def test_single_math_symbol_with_math_mode() -> None:
    """A 1-byte math symbol with math mode on returns True."""
    assert ls_task_math_mode(b"+", math_mode_enabled=True) is True


def test_math_mode_off_always_false() -> None:
    """With math mode off, every input returns False."""
    assert ls_task_math_mode(b"+", math_mode_enabled=False) is False
    assert ls_task_math_mode(b"=", math_mode_enabled=False) is False


def test_multi_byte_input_false() -> None:
    """Words longer than 1 byte never match (math mode is 1-char only)."""
    assert ls_task_math_mode(b"++", math_mode_enabled=True) is False


def test_empty_input_false() -> None:
    """Empty input is not a math symbol."""
    assert ls_task_math_mode(b"", math_mode_enabled=True) is False


def test_non_math_single_char_false() -> None:
    """A letter (not in math_table) with math mode on still returns False."""
    assert ls_task_math_mode(b"a", math_mode_enabled=True) is False


def test_list_int_input() -> None:
    """``word`` as ``list[int]`` is also accepted."""
    assert ls_task_math_mode([ord("+")], math_mode_enabled=True) is True
