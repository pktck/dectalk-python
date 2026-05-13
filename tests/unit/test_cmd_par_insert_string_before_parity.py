"""C-source parity test for ``par_insert_string_before`` against par_pars1.c.

Re-parses the C function body and asserts structural patterns
match the Python port:

- call to :func:`par_build_string_from_rule` with the combined
  ``BIN_INSERT | BIN_BEFORE_FLAG`` state code,
- right-shift loop that moves the matched span ``length`` bytes
  forward,
- prefix copy via ``memcpy``,
- index clearing from ``PAR_MAX_OUTPUT_ARRAY - 1``,
- ``output_offset += length`` update.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_EXACT
from dectalk.cmd.par_insert_string_before import par_insert_string_before
from dectalk.cmd.par_limits import PAR_MAX_OUTPUT_ARRAY
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the ``par_insert_string_before`` definition.

    Uses brace-depth tracking rather than a regex like ``[^;{]+?`` because
    the parameter list spans a ``#ifndef GERMAN_COMPOUND_NOUNS`` block
    and the simpler regex would either greedy-match too far or fall over
    on the preprocessor lines.
    """
    text = _read_par_pars1_c()
    # Anchor on the definition (signature line followed eventually by `{`,
    # skipping the earlier forward declaration which ends in `;`).
    definitions: list[int] = []
    for match in re.finditer(r"^void\s+par_insert_string_before\s*\(", text, re.MULTILINE):
        # Walk forward from the match looking for either `;` (declaration)
        # or `{` (definition), tracking parenthesis depth.
        i = match.end()
        paren_depth = 1
        while i < len(text) and paren_depth > 0:
            ch = text[i]
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
            i += 1
        # After the closing paren, find the next ``;`` or ``{`` (skipping
        # whitespace and preprocessor noise).
        while i < len(text) and text[i] not in ";{":
            i += 1
        if i < len(text) and text[i] == "{":
            definitions.append(match.start())
    assert definitions, "par_insert_string_before definition not found"
    start = definitions[-1]

    # Walk braces to find the matching close.
    body_start = text.index("{", start)
    depth = 1
    i = body_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start:i]


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    return [IndexData() for _ in range(n)]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_present() -> None:
    """The C signature exists in the source."""
    text = _read_par_pars1_c()
    assert re.search(r"void\s+par_insert_string_before\s*\(", text) is not None


def test_calls_par_build_string_with_before() -> None:
    """The build call uses BIN_INSERT|BIN_BEFORE_FLAG (or BIN_BEFORE)."""
    body = _extract_body()
    assert "par_build_string_from_rule" in body
    # The Linux build uses GERMAN_COMPOUND_NOUNS — combined opcode form.
    assert re.search(r"BIN_INSERT\s*\|\s*BIN_BEFORE_FLAG", body) is not None
    # The non-GERMAN branch uses BIN_BEFORE alone — kept for completeness.
    assert "BIN_BEFORE" in body
    # Both forms must thread the address of `length` and `in_rule_index`.
    assert re.search(r"&\s*length", body) is not None
    assert "in_rule_index" in body


def test_right_shift_loop_inserts_before_output_pos() -> None:
    """``for (i = j-1; i >= output_pos; i--)`` shifts the tail rightward."""
    body = _extract_body()
    # j = output_pos + output_offset.
    assert (
        re.search(
            r"j\s*=\s*ret_value\s*->\s*output_pos\s*\+\s*ret_value\s*->\s*output_offset",
            body,
        )
        is not None
    )
    # Reverse loop bounded by output_pos.
    assert (
        re.search(
            r"for\s*\(\s*i\s*=\s*j\s*-\s*1\s*;\s*i\s*>=\s*ret_value\s*->\s*output_pos\s*;\s*i\s*--\s*\)",
            body,
        )
        is not None
    )
    # The shift body writes output_array[i+length] = output_array[i].
    assert (
        re.search(
            r"output_array\s*\[\s*i\s*\+\s*length\s*\]\s*=\s*output_array\s*\[\s*i\s*\]",
            body,
        )
        is not None
    )


def test_memcpy_into_output_pos_prefix() -> None:
    """``memcpy(output_array + output_pos, buf, length)`` drops the prefix."""
    body = _extract_body()
    assert (
        re.search(
            r"memcpy\s*\(\s*\(?\s*output_array\s*\+\s*\(?\s*ret_value\s*->\s*output_pos",
            body,
        )
        is not None
    )


def test_updates_indexes_for_shifted_entries() -> None:
    """``par_copy_index(output_indexes, i+length, output_indexes, i)``."""
    body = _extract_body()
    assert (
        re.search(
            r"par_copy_index\s*\(\s*output_indexes\s*,\s*i\s*\+\s*length\s*,\s*"
            r"output_indexes\s*,\s*i\s*\)",
            body,
        )
        is not None
    )


def test_clears_indexes_via_par_max_output_array_minus_one() -> None:
    """Index markers in the inserted range get cleared from the trash slot."""
    body = _extract_body()
    assert "PAR_MAX_OUTPUT_ARRAY" in body
    assert re.search(r"PAR_MAX_OUTPUT_ARRAY\s*-\s*1", body) is not None


def test_output_offset_grows_by_length() -> None:
    """``ret_value->output_offset += length``."""
    body = _extract_body()
    assert (
        re.search(
            r"ret_value\s*->\s*output_offset\s*\+=\s*length",
            body,
        )
        is not None
    )


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def _make_insert_before_rule(literal: bytes) -> bytearray:
    """Build a rule whose BIN_BEFORE action materialises ``literal``.

    Layout: [BIN_BEFORE][_][end_of_action][_][BIN_EXACT][len][literal...]
    ``end_of_action`` is the index of the last byte the build loop reads.
    """
    rule = bytearray(20)
    rule[0] = 0x1C  # BIN_BEFORE opcode
    rule[2] = 4 + 1 + len(literal)  # end_of_action = last literal byte
    rule[4] = BIN_EXACT
    rule[5] = len(literal)
    rule[6 : 6 + len(literal)] = literal
    return rule


def test_inserts_two_char_prefix_before_three_char_span() -> None:
    """A 2-char built string slots before a 3-char span and shifts the tail.

    Starting state: output_array = b"AB" + b"CDE" + tail, output_pos=2,
    output_offset=3 (the matched span is "CDE"). The 2-byte build "XY"
    should land at indices 2..3 and push "CDE" to 4..6.
    """
    rule = _make_insert_before_rule(b"XY")
    out = bytearray(b"AB" + b"CDE" + b"\x00" * 50)
    ret = ReturnValue(output_pos=2, output_offset=3, rule=4)
    par_insert_string_before(
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
    # The inserted bytes appear at indices 2..3.
    assert bytes(out[2:4]) == b"XY"
    # The original "CDE" shifts to 4..6.
    assert bytes(out[4:7]) == b"CDE"
    # The prefix "AB" is unchanged.
    assert bytes(out[:2]) == b"AB"
    # ret.value is NOT FATAL_FAIL on success.
    assert ret.value != FATAL_FAIL


def test_output_offset_incremented_by_inserted_length() -> None:
    """``output_offset`` grows by ``length`` of the inserted string."""
    rule = _make_insert_before_rule(b"XYZ")
    out = bytearray(b"AB" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=2, rule=4)
    par_insert_string_before(
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
    assert ret.output_offset == 5
    assert bytes(out[:5]) == b"XYZAB"
    assert ret.value != FATAL_FAIL


def test_ret_value_not_fatal_fail_on_success() -> None:
    """A well-formed rule body leaves ``ret_value.value`` non-FATAL."""
    rule = _make_insert_before_rule(b"X")
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string_before(
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
    assert ret.value != FATAL_FAIL
    assert bytes(out[:4]) == b"XABC"


def test_index_markers_shift_with_existing_chars() -> None:
    """Existing index markers travel rightward with their characters."""
    rule = _make_insert_before_rule(b"X")
    out = bytearray(b"ABC" + b"\x00" * 50)
    indexes = _empty_indexes()
    # Marker on position 1 (the 'B' in 'ABC').
    indexes[1].index = [123, 0, 0]
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string_before(
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
    # After the shift: out[2] should now be 'B' and indexes[2] carries [123,0,0].
    assert out[2] == ord("B")
    assert indexes[2].index == [123, 0, 0]
    # The newly-inserted slot at position 0 has no index marker.
    assert indexes[0].index == [0, 0, 0]


def test_fatal_fail_propagates_from_build() -> None:
    """A bad opcode in the rule body sets ``ret_value.value = FATAL_FAIL``."""
    rule = bytearray(20)
    rule[0] = 0x1C
    rule[2] = 5
    rule[4] = 0x05  # BIN_CONSONANT — not allowed in the build loop
    rule[5] = 0
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string_before(
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
    assert ret.value == FATAL_FAIL
