"""Verify par_skip_white_space matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_skip_white_space import par_skip_white_space
from dectalk.cmd.par_structs import IndexData, ReturnValue


def _empty_indexes(n: int) -> list[IndexData]:
    """Build a list of ``n`` default IndexData records."""
    return [IndexData() for _ in range(n)]


def test_no_whitespace_returns_zero_and_no_offset() -> None:
    """If the cursor isn't on whitespace, offsets stay unchanged."""
    inp = b"abc\x00"
    inp_idx = _empty_indexes(10)
    out = bytearray(10)
    out_idx = _empty_indexes(10)
    rv = ReturnValue(input_pos=0)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    assert res == 0
    assert rv.input_offset == 0
    assert rv.output_offset == 0


def test_single_space_is_copied() -> None:
    """One space at the cursor is consumed and copied to output."""
    inp = b"a b\x00"
    inp_idx = _empty_indexes(10)
    out = bytearray(10)
    out_idx = _empty_indexes(10)
    rv = ReturnValue(input_pos=1)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    assert res == 0
    assert rv.input_offset == 1
    assert rv.output_offset == 1
    assert out[0] == ord(" ")


def test_run_of_spaces_emits_only_first() -> None:
    """A run of 3 spaces consumes 3 bytes but emits only 1 (the first)."""
    inp = b"a   b\x00"
    inp_idx = _empty_indexes(20)
    out = bytearray(20)
    out_idx = _empty_indexes(20)
    rv = ReturnValue(input_pos=1)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    assert res == 0
    assert rv.input_offset == 3
    assert rv.output_offset == 1


def test_nul_terminator_returns_minus_one() -> None:
    """Hitting NUL after a whitespace run returns -1."""
    inp = b"   \x00"
    inp_idx = _empty_indexes(20)
    out = bytearray(20)
    out_idx = _empty_indexes(20)
    rv = ReturnValue(input_pos=0)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    assert res == -1
    assert rv.input_offset == 3


def test_tab_is_not_in_type_white() -> None:
    """Tab (0x09) is NOT classified as TYPE_white in parser_char_types."""
    inp = b"\tabc"
    inp_idx = _empty_indexes(10)
    out = bytearray(10)
    out_idx = _empty_indexes(10)
    rv = ReturnValue(input_pos=0)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    # Tab is in TYPE_quot, not TYPE_white, so the scan stops immediately.
    assert res == 0
    assert rv.input_offset == 0


def test_index_marked_position_inside_run_is_copied() -> None:
    """An index-marked whitespace inside the run also emits."""
    inp = b"a   b\x00"
    inp_idx = _empty_indexes(20)
    # Place an index marker on the *second* space (input pos 2).
    inp_idx[2].index = [0, 1, 0]
    out = bytearray(20)
    out_idx = _empty_indexes(20)
    rv = ReturnValue(input_pos=1)
    par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    # The first space (i=0) emits unconditionally. The second emits
    # because of the index marker.
    assert rv.output_offset == 2
    # Index propagated to output position 1.
    assert out_idx[1].index == [0, 1, 0]


def test_starts_from_input_offset() -> None:
    """input_offset is added to input_pos for the start position."""
    inp = b"xy zz"
    inp_idx = _empty_indexes(20)
    out = bytearray(20)
    out_idx = _empty_indexes(20)
    rv = ReturnValue(input_pos=0, input_offset=2)
    res = par_skip_white_space(inp, inp_idx, out, out_idx, rv)
    assert res == 0
    assert rv.input_offset == 3
