"""Verify par_initialize_arrays / par_initialize_variables match par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_initialize import par_initialize_arrays, par_initialize_variables
from dectalk.cmd.par_structs import PAR_MAX_ARRAYS, PAR_MAX_MATCH_ARRAY, MatchArrays


def test_initialize_arrays_zeros_all_slots() -> None:
    """Every byte of every slot becomes zero."""
    match = MatchArrays()
    # Pre-fill with non-zero bytes.
    for i in range(PAR_MAX_ARRAYS):
        for j in range(PAR_MAX_MATCH_ARRAY):
            match.array[i][j] = 0xAB
    par_initialize_arrays(match)
    for i in range(PAR_MAX_ARRAYS):
        for j in range(PAR_MAX_MATCH_ARRAY):
            assert match.array[i][j] == 0, f"slot {i} byte {j} not zeroed"


def test_initialize_arrays_handles_default_state() -> None:
    """Default-constructed match arrays start zero and stay zero."""
    match = MatchArrays()
    par_initialize_arrays(match)
    for arr in match.array:
        assert all(b == 0 for b in arr)


def test_initialize_variables_zeros_all_three() -> None:
    """The input/output/dict-hit arrays are all zeroed."""
    inp = bytearray(b"\xaa" * 10)
    out = bytearray(b"\xbb" * 10)
    dict_hit = bytearray(b"\xcc" * 10)
    par_initialize_variables(inp, out, dict_hit)
    assert all(b == 0 for b in inp)
    assert all(b == 0 for b in out)
    assert all(b == 0 for b in dict_hit)


def test_initialize_variables_handles_oversized_arrays() -> None:
    """Arrays larger than PAR_MAX_* are left intact past the limit."""
    from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY  # noqa: PLC0415

    out = bytearray(b"\xaa" * (PAR_MAX_OUTPUT_ARRAY + 10))
    # Dummy input/dict_hit so we can focus on the output bound.
    inp = bytearray(0)
    dict_hit = bytearray(0)
    par_initialize_variables(inp, out, dict_hit)
    # First PAR_MAX_OUTPUT_ARRAY bytes zeroed.
    assert all(b == 0 for b in out[:PAR_MAX_OUTPUT_ARRAY])
    # Tail bytes preserved.
    assert all(b == 0xAA for b in out[PAR_MAX_OUTPUT_ARRAY:])
