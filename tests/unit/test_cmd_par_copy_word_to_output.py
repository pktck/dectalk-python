"""Verify par_copy_word_to_output matches par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_copy_word_to_output import par_copy_word_to_output
from dectalk.cmd.par_structs import IndexData, ReturnValue


def _empty_indexes(n: int) -> list[IndexData]:
    """Build a list of ``n`` default IndexData records."""
    return [IndexData() for _ in range(n)]


def test_copies_word_until_whitespace() -> None:
    """Non-whitespace bytes are copied verbatim until a space."""
    inp = b"hello world\x00"
    out = bytearray(20)
    rv = ReturnValue(input_pos=0)
    res = par_copy_word_to_output(inp, out, _empty_indexes(20), _empty_indexes(20), rv)
    assert res == 0
    assert bytes(out[:5]) == b"hello"
    assert rv.input_offset == 5
    assert rv.output_offset == 5


def test_nul_terminator_returns_minus_one() -> None:
    """A word ending in NUL returns -1."""
    inp = b"hello\x00"
    out = bytearray(20)
    rv = ReturnValue(input_pos=0)
    res = par_copy_word_to_output(inp, out, _empty_indexes(20), _empty_indexes(20), rv)
    assert res == -1
    assert rv.input_offset == 5
    assert rv.output_offset == 5


def test_empty_word_at_start_no_progress() -> None:
    """A whitespace byte at the cursor produces zero progress."""
    inp = b" hello\x00"
    out = bytearray(20)
    rv = ReturnValue(input_pos=0)
    res = par_copy_word_to_output(inp, out, _empty_indexes(20), _empty_indexes(20), rv)
    assert res == 0
    assert rv.input_offset == 0
    assert rv.output_offset == 0


def test_index_markers_propagated_per_byte() -> None:
    """Each byte's index marker is copied to the output."""
    inp = b"abc def"
    inp_idx = _empty_indexes(20)
    inp_idx[0].index = [9, 0, 0]
    inp_idx[2].index = [0, 5, 0]
    out_idx = _empty_indexes(20)
    out = bytearray(20)
    rv = ReturnValue(input_pos=0)
    par_copy_word_to_output(inp, out, inp_idx, out_idx, rv)
    assert out_idx[0].index == [9, 0, 0]
    assert out_idx[2].index == [0, 5, 0]


def test_starts_from_input_offset() -> None:
    """input_offset added to input_pos for the start position."""
    inp = b"xy hello"
    out = bytearray(20)
    rv = ReturnValue(input_pos=0, input_offset=3)
    res = par_copy_word_to_output(inp, out, _empty_indexes(20), _empty_indexes(20), rv)
    assert res == -1
    assert bytes(out[:5]) == b"hello"
    assert rv.input_offset == 8


def test_output_offset_tracked() -> None:
    """output_offset receives the chars-written count."""
    inp = b"word stop"
    out = bytearray(20)
    rv = ReturnValue(input_pos=0, output_pos=5)
    par_copy_word_to_output(inp, out, _empty_indexes(20), _empty_indexes(20), rv)
    assert rv.output_offset == 4
    # Output written starting at output_pos + output_offset = 5+0 → bytes 5..8.
    assert bytes(out[5:9]) == b"word"
