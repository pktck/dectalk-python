"""Verify ls_util_is_name matches the ACNA-branch logic in ls_util.c."""

from __future__ import annotations

from dectalk.kernel.mode_flags import MODE_NAME, PRON_ACNA_NAME
from dectalk.lts.name_check import ls_util_is_name


def test_acna_disabled_always_false() -> None:
    """When ``acna_enabled=False`` (the ``#else`` branch), result is False."""
    is_name, new_flag = ls_util_is_name(b"Hello", acna_enabled=False)
    assert is_name is False
    assert new_flag == 0


def test_already_marked_name() -> None:
    """If ``PRON_ACNA_NAME`` is already set, returns True without changes."""
    is_name, new_flag = ls_util_is_name(b"foo", pron_flag=PRON_ACNA_NAME)
    assert is_name is True
    assert new_flag == PRON_ACNA_NAME


def test_preamble_command_3_forces_name() -> None:
    """``[:name on]`` (preamble cmd 3) sets ``PRON_ACNA_NAME``."""
    is_name, new_flag = ls_util_is_name(b"x", last_preamble_command=3)
    assert is_name is True
    assert new_flag & PRON_ACNA_NAME


def test_mode_name_off_returns_true() -> None:
    """If ``MODE_NAME`` bit is off, every word is treated as a name."""
    is_name, new_flag = ls_util_is_name(b"hello", mode_flag=0)
    assert is_name is True
    # Doesn't set PRON_ACNA_NAME — just returns True.
    assert new_flag == 0


def test_first_word_returns_false() -> None:
    """``cur_word_index == 0`` (first word) cannot be a name."""
    is_name, _ = ls_util_is_name(
        b"Hello",
        mode_flag=MODE_NAME,
        cur_word_index=0,
    )
    assert is_name is False


def test_lowercase_first_letter_not_a_name() -> None:
    """Words starting with lowercase aren't names."""
    is_name, _ = ls_util_is_name(
        b"hello",
        mode_flag=MODE_NAME,
        cur_word_index=1,
    )
    assert is_name is False


def test_capitalized_then_lowercase_is_name() -> None:
    """``Hello`` (cap + tail lowercase) at word index > 0 is a name."""
    is_name, new_flag = ls_util_is_name(
        b"Hello",
        mode_flag=MODE_NAME,
        cur_word_index=1,
    )
    assert is_name is True
    assert new_flag & PRON_ACNA_NAME


def test_all_caps_not_a_name() -> None:
    """``HELLO`` (all caps) isn't a name — tail must be lowercase."""
    is_name, _ = ls_util_is_name(
        b"HELLO",
        mode_flag=MODE_NAME,
        cur_word_index=1,
    )
    assert is_name is False


def test_empty_word_not_a_name() -> None:
    """Empty word slice with mode_name on isn't a name."""
    is_name, _ = ls_util_is_name(
        b"",
        mode_flag=MODE_NAME,
        cur_word_index=1,
    )
    assert is_name is False
