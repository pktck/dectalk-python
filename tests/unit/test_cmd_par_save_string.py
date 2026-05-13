"""Verify par_save_string matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_save_string import par_save_string
from dectalk.cmd.par_structs import MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL, SUCCESS


def test_saves_span_into_slot() -> None:
    """The span ``output_pos..output_pos+output_offset`` is copied into slot."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=2, output_offset=3, value=SUCCESS)
    par_save_string(b"abhello", 0, match, rv)
    assert match.array[0][:3] == b"hel"
    assert match.array[0][3] == 0  # NUL terminator.
    assert rv.value == SUCCESS


def test_negative_slot_fails() -> None:
    """num < 0 sets FATAL_FAIL."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_save_string(b"abc", -1, match, rv)
    assert rv.value == FATAL_FAIL


def test_out_of_range_slot_fails() -> None:
    """num > PAR_MAX_ARRAYS sets FATAL_FAIL."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_save_string(b"abc", 99, match, rv)
    assert rv.value == FATAL_FAIL


def test_optional_minus_one_is_noop() -> None:
    """When optional==-1, the save is skipped."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=0, output_offset=3, optional=-1, value=SUCCESS)
    par_save_string(b"abc", 0, match, rv)
    assert match.array[0][:3] == b"\x00\x00\x00"
    assert rv.value == SUCCESS


def test_span_too_long_returns_fail() -> None:
    """An output_offset >= PAR_MAX_MATCH_ARRAY returns FAIL."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=0, output_offset=30, value=SUCCESS)
    par_save_string(b"x" * 30, 0, match, rv)
    assert rv.value == FAIL


def test_multiple_saves_to_different_slots() -> None:
    """Each slot is independent."""
    match = MatchArrays()
    rv1 = ReturnValue(output_pos=0, output_offset=2, value=SUCCESS)
    par_save_string(b"hi", 0, match, rv1)
    rv2 = ReturnValue(output_pos=0, output_offset=3, value=SUCCESS)
    par_save_string(b"bye", 5, match, rv2)
    assert match.array[0][:2] == b"hi"
    assert match.array[5][:3] == b"bye"


def test_overwrite_clears_trailing_bytes() -> None:
    """Re-saving with a shorter span clears the previous longer content."""
    match = MatchArrays()
    rv = ReturnValue(output_pos=0, output_offset=4, value=SUCCESS)
    par_save_string(b"long", 0, match, rv)
    assert match.array[0][:4] == b"long"
    rv2 = ReturnValue(output_pos=0, output_offset=2, value=SUCCESS)
    par_save_string(b"hi", 0, match, rv2)
    assert match.array[0][:2] == b"hi"
    assert match.array[0][2] == 0  # Was 'n'; now zeroed.
