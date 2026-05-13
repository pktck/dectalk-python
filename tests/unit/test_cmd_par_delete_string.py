"""Verify par_delete_string matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_delete_string import par_delete_string
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import IndexData, ReturnValue
from dectalk.cmd.rule_states import PAR_INDEX_DUMMY_CHAR


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    """Build a list of ``n`` default IndexData records.

    Default size is :data:`PAR_MAX_OUTPUT_ARRAY` because
    :func:`par_delete_string` writes to ``output_indexes[PAR_MAX_OUTPUT_ARRAY-1]``
    as a trash-bin slot.
    """
    return [IndexData() for _ in range(n)]


def test_zeroes_span_when_optional_not_minus_one() -> None:
    """The matched span is zeroed and output_offset reset to 0."""
    out = bytearray(b"abcdefgh")
    rv = ReturnValue(output_pos=2, output_offset=4)
    par_delete_string(out, _empty_indexes(), rv)
    assert bytes(out) == b"ab\x00\x00\x00\x00gh"
    assert rv.output_offset == 0


def test_optional_minus_one_does_not_zero() -> None:
    """When optional == -1, the span is left intact (output_offset stays)."""
    out = bytearray(b"abcdefgh")
    rv = ReturnValue(output_pos=2, output_offset=4, optional=-1)
    par_delete_string(out, _empty_indexes(), rv)
    assert bytes(out) == b"abcdefgh"
    assert rv.output_offset == 4


def test_preserves_index_marked_positions() -> None:
    """Bytes carrying an index marker get PAR_INDEX_DUMMY_CHAR instead."""
    out = bytearray(b"abcdefgh")
    indexes = _empty_indexes()
    indexes[3].index = [0, 1, 0]  # Marker on the 'd' (output_pos=2 + offset 1).
    rv = ReturnValue(output_pos=2, output_offset=4)
    par_delete_string(out, indexes, rv)
    # 'c', 'e', 'f' get zeroed; 'd' was zeroed but then written as dummy.
    assert out[2] == 0
    assert out[3] == PAR_INDEX_DUMMY_CHAR
    assert out[4] == 0
    assert out[5] == 0
    # Index migrated from position 3 to position 2 (the head).
    assert indexes[2].index == [0, 1, 0]


def test_output_offset_bumps_for_each_preserved_index() -> None:
    """Each preserved index increments output_offset by 1."""
    out = bytearray(b"abcdefgh")
    indexes = _empty_indexes()
    indexes[3].index = [1, 0, 0]
    indexes[5].index = [2, 0, 0]
    rv = ReturnValue(output_pos=2, output_offset=4)
    par_delete_string(out, indexes, rv)
    # Two indices preserved → output_offset = 2.
    assert rv.output_offset == 2


def test_no_indexes_means_clean_delete() -> None:
    """With no indices in the span, output_offset returns to 0 and stays."""
    out = bytearray(b"abcde")
    rv = ReturnValue(output_pos=1, output_offset=3)
    par_delete_string(out, _empty_indexes(), rv)
    assert rv.output_offset == 0


def test_empty_output_array_sets_fatal_fail() -> None:
    """A zero-length output is the defensive NULL-array path."""
    rv = ReturnValue()
    par_delete_string(bytearray(), _empty_indexes(), rv)
    from dectalk.cmd.rule_states import FATAL_FAIL  # noqa: PLC0415

    assert rv.value == FATAL_FAIL
