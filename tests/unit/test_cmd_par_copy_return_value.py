"""Verify par_copy_return_value matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_copy_return_value import par_copy_return_value
from dectalk.cmd.par_structs import ReturnValue


def test_copies_all_scalar_fields() -> None:
    """Every scalar field is copied over."""
    src = ReturnValue(
        input_pos=1,
        input_offset=2,
        output_pos=3,
        output_offset=4,
        rule=5,
        value=6,
        optional=7,
        state=8,
        parser_flag=9,
    )
    dest = ReturnValue()
    par_copy_return_value(dest, src)
    assert dest.input_pos == 1
    assert dest.input_offset == 2
    assert dest.output_pos == 3
    assert dest.output_offset == 4
    assert dest.rule == 5
    assert dest.value == 6
    assert dest.optional == 7
    assert dest.state == 8
    assert dest.parser_flag == 9


def test_prev_pointer_aliased() -> None:
    """``prev`` is copied by reference (identity preserved)."""
    parent = ReturnValue(input_pos=99)
    src = ReturnValue(prev=parent)
    dest = ReturnValue()
    par_copy_return_value(dest, src)
    assert dest.prev is parent


def test_src_unchanged_after_copy() -> None:
    """``src`` is left untouched."""
    src = ReturnValue(input_pos=42)
    dest = ReturnValue(input_pos=0)
    par_copy_return_value(dest, src)
    assert src.input_pos == 42


def test_dest_overwrites_existing_values() -> None:
    """Dest's existing values are replaced."""
    dest = ReturnValue(input_pos=999, value=999)
    src = ReturnValue(input_pos=1, value=2)
    par_copy_return_value(dest, src)
    assert dest.input_pos == 1
    assert dest.value == 2


def test_self_copy_is_noop() -> None:
    """Copying a record to itself leaves it unchanged."""
    record = ReturnValue(input_pos=5, value=7)
    par_copy_return_value(record, record)
    assert record.input_pos == 5
    assert record.value == 7


def test_independent_after_copy() -> None:
    """Mutating dest after copy doesn't affect src."""
    src = ReturnValue(input_pos=10)
    dest = ReturnValue()
    par_copy_return_value(dest, src)
    dest.input_pos = 999
    assert src.input_pos == 10
