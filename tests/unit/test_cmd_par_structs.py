"""Verify the par_def.h parser-state dataclasses."""

from __future__ import annotations

from dectalk.cmd.par_structs import (
    PAR_MAX_ARRAYS,
    PAR_MAX_MATCH_ARRAY,
    DictPointers,
    IndexData,
    MatchArrays,
    RangeValue,
    ReturnValue,
)


def test_constants() -> None:
    """PAR_MAX_ARRAYS=10 / PAR_MAX_MATCH_ARRAY=30 per par_def.h."""
    assert PAR_MAX_ARRAYS == 10
    assert PAR_MAX_MATCH_ARRAY == 30


def test_dict_pointers_defaults() -> None:
    """DictPointers defaults to all-zero."""
    dp = DictPointers()
    assert dp.start == 0
    assert dp.end == 0
    assert dp.num_entries == 0


def test_return_value_defaults() -> None:
    """ReturnValue defaults to all-zero, prev=None."""
    rv = ReturnValue()
    assert rv.input_pos == 0
    assert rv.input_offset == 0
    assert rv.value == 0
    assert rv.parser_flag == 0
    assert rv.prev is None


def test_return_value_chain() -> None:
    """ReturnValue.prev wires up to the caller's frame for lookahead."""
    outer = ReturnValue(input_pos=5)
    inner = ReturnValue(input_pos=10, prev=outer)
    assert inner.prev is outer
    assert inner.prev.input_pos == 5


def test_range_value_defaults() -> None:
    """RangeValue defaults to all-zero."""
    rv = RangeValue()
    assert rv.start == 0
    assert rv.end == 0
    assert rv.min == 0
    assert rv.range_set == 0


def test_match_arrays_layout() -> None:
    """MatchArrays.array has 10 bytearrays of length 30 each."""
    ma = MatchArrays()
    assert len(ma.array) == PAR_MAX_ARRAYS
    for buf in ma.array:
        assert isinstance(buf, bytearray)
        assert len(buf) == PAR_MAX_MATCH_ARRAY


def test_match_arrays_independent() -> None:
    """Each MatchArrays instance has its own buffers (no sharing)."""
    ma1 = MatchArrays()
    ma2 = MatchArrays()
    ma1.array[0][0] = 0x42
    assert ma2.array[0][0] == 0  # not 0x42


def test_index_data_defaults() -> None:
    """IndexData has a 3-element index list of zeroes."""
    idx = IndexData()
    assert idx.index == [0, 0, 0]


def test_index_data_independent() -> None:
    """Each IndexData instance has its own list."""
    a = IndexData()
    b = IndexData()
    a.index[0] = 5
    assert b.index[0] == 0
