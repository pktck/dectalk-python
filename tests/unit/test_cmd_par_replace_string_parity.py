"""C-source parity test for ``par_replace_string`` against par_pars1.c.

Re-parses the C function body and asserts structural patterns
match the Python port:

- the call into :func:`par_build_string_from_rule` with the
  ``BIN_REPLACE`` opcode,
- the index-migration loop with a space-anchor heuristic,
- the final ``strcpy`` + ``par_copy_index_list`` + ``output_offset``
  update.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_EXACT
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_replace_string import par_replace_string
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL, PAR_INDEX_DUMMY_CHAR

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the C function body of ``par_replace_string``.

    Locates the definition (not the forward declaration) by walking
    every ``void par_replace_string`` occurrence and picking the one
    immediately followed by an opening brace. The signature spans an
    ``#ifndef GERMAN_COMPOUND_NOUNS`` block, so we cannot use the
    usual ``[^;{]+?`` no-semicolons-no-braces parameter pattern --
    instead we anchor on the opening brace via brace-depth tracking.
    """
    text = _read_par_pars1_c()
    for match in re.finditer(r"void\s+par_replace_string\b", text):
        # Skip the prototype (followed by ';') and the function-table
        # entries -- only the definition has a '{' after the param list.
        brace_idx = text.find("{", match.end())
        semi_idx = text.find(";", match.end())
        if brace_idx == -1 or (semi_idx != -1 and semi_idx < brace_idx):
            continue
        # Walk the brace-balanced body.
        depth = 1
        i = brace_idx + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        assert depth == 0, "unbalanced braces in par_replace_string body"
        return text[brace_idx + 1 : i - 1]
    raise AssertionError("par_replace_string definition not found")


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    return [IndexData() for _ in range(n)]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_present() -> None:
    """The C signature has the expected parameter list."""
    text = _read_par_pars1_c()
    assert re.search(
        r"void\s+par_replace_string\s*\(\s*"
        r"unsigned\s+char\s*\*\s*current_rule\s*,\s*"
        r"unsigned\s+char\s*\*\s*input_array\s*,\s*"
        r"unsigned\s+char\s*\*\s*output_array\s*,\s*"
        r"pindex_data_t\s+input_indexes\s*,\s*"
        r"pindex_data_t\s+output_indexes\s*,\s*"
        r"pmatch_arrays_t\s+match_array",
        text,
    )


def test_calls_par_build_string_from_rule_with_bin_replace() -> None:
    """The body materialises the replacement via par_build_string_from_rule."""
    body = _extract_body()
    assert "par_build_string_from_rule" in body
    assert "BIN_REPLACE" in body


def test_index_migration_anchors_on_space() -> None:
    """The index-migration loop searches buf for a space character."""
    body = _extract_body()
    # buf[j]!=' ' loop
    assert re.search(r"buf\s*\[\s*j\s*\]\s*!=\s*'\s'", body)


def test_par_index_dummy_char_used_for_marker_replacement() -> None:
    """PAR_INDEX_DUMMY_CHAR replaces the byte where an index is anchored."""
    body = _extract_body()
    assert "PAR_INDEX_DUMMY_CHAR" in body


def test_strcpy_writes_into_output() -> None:
    """The final write uses strcpy(output_array + output_pos, buf)."""
    body = _extract_body()
    assert "strcpy" in body
    assert re.search(
        r"strcpy\s*\(\s*\(?\s*output_array\s*\+\s*\(?\s*ret_value\s*->\s*output_pos",
        body,
    )


def test_par_copy_index_list_after_strcpy() -> None:
    """par_copy_index_list copies the per-position index markers."""
    body = _extract_body()
    assert "par_copy_index_list" in body


def test_output_offset_updated_to_length() -> None:
    """``ret_value->output_offset = length`` at the end."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*output_offset\s*=\s*length",
        body,
    )


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_replace_overwrites_span() -> None:
    """A simple BIN_EXACT body overwrites the matched span."""
    rule = bytearray(20)
    rule[0] = 0x19  # BIN_REPLACE
    rule[2] = 8  # end_of_action: last byte of body
    rule[4] = BIN_EXACT
    rule[5] = 3
    rule[6] = ord("N")
    rule[7] = ord("E")
    rule[8] = ord("W")
    out = bytearray(b"abXYZcd" + b"\x00" * 20)
    ret = ReturnValue(output_pos=2, output_offset=3, rule=4)
    par_replace_string(
        bytes(rule),
        bytearray(),
        out,
        _empty_indexes(),
        _empty_indexes(),
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert bytes(out[:5]) == b"abNEW"
    assert ret.output_offset == 3
    # Success path -- the function never raises FATAL_FAIL on a valid rule.
    assert ret.value != FATAL_FAIL


def test_replace_resets_output_offset_to_length() -> None:
    """``output_offset`` becomes the new built-string length."""
    rule = bytearray(20)
    rule[0] = 0x19
    rule[2] = 6
    rule[4] = BIN_EXACT
    rule[5] = 1
    rule[6] = ord("!")
    out = bytearray(b"abcdef" + b"\x00" * 20)
    ret = ReturnValue(output_pos=0, output_offset=5, rule=4)
    par_replace_string(
        bytes(rule),
        bytearray(),
        out,
        _empty_indexes(),
        _empty_indexes(),
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    assert ret.output_offset == 1


def test_replace_migrates_index_to_space_anchor() -> None:
    """An index inside the replaced span moves to a space in the new string."""
    rule = bytearray(30)
    rule[0] = 0x19
    rule[2] = 10
    rule[4] = BIN_EXACT
    rule[5] = 5
    rule[6:11] = b"X Y Z"  # built string contains a space at index 1 and 3
    out = bytearray(b"abXX" + b"\x00" * 20)
    indexes = _empty_indexes()
    # Place an index marker on the second 'X' of the replaced span (position 3).
    indexes[3].index = [99, 0, 0]
    ret = ReturnValue(output_pos=2, output_offset=2, rule=4)
    par_replace_string(
        bytes(rule),
        bytearray(),
        out,
        _empty_indexes(),
        indexes,
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    # The space in 'X Y Z' is at position 1 of buf -> output_pos+1=3.
    # That position is now PAR_INDEX_DUMMY_CHAR, with the index migrated.
    assert out[3] == PAR_INDEX_DUMMY_CHAR
    assert indexes[3].index == [99, 0, 0]


def test_replace_falls_back_to_dummy_when_no_space() -> None:
    """When no space exists in the built string, a dummy character is appended."""
    rule = bytearray(20)
    rule[0] = 0x19
    rule[2] = 8
    rule[4] = BIN_EXACT
    rule[5] = 3
    rule[6:9] = b"NEW"
    out = bytearray(b"abXY" + b"\x00" * 20)
    indexes = _empty_indexes()
    indexes[2].index = [42, 0, 0]
    ret = ReturnValue(output_pos=2, output_offset=2, rule=4)
    par_replace_string(
        bytes(rule),
        bytearray(),
        out,
        _empty_indexes(),
        indexes,
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    # No space in 'NEW' -> dummy char appended.
    # output_offset = length(3) + 1(appended dummy) = 4.
    assert ret.output_offset == 4
    # The appended dummy lives at the end of the built string (output_pos+3).
    assert out[5] == PAR_INDEX_DUMMY_CHAR
