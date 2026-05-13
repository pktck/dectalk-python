"""C-source parity test for ``par_insert_string`` against par_pars1.c.

Re-parses the C function body and asserts structural patterns
match the Python port:

- the GERMAN_COMPOUND_NOUNS dispatch on BIN_AFTER_FLAG /
  BIN_BEFORE_FLAG bits in ``insert_operation_flags``,
- the call to :func:`par_build_string_from_rule` with the
  ``BIN_INSERT`` state code,
- the reverse-direction interleave loop that mutates
  ``output_array`` in place from the tail end backward.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_AFTER_FLAG, BIN_BEFORE_FLAG, BIN_EXACT
from dectalk.cmd.par_insert_string import par_insert_string
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
    """Return the par_insert_string function body via brace-depth tracking.

    The C parameter list spans an ``#ifndef GERMAN_COMPOUND_NOUNS`` block, so
    a lazy ``[^;{]+?`` regex over the signature cannot reliably anchor on
    ``)``. We locate ``void par_insert_string(`` with a word-boundary
    anchor (to avoid the ``_before``/``_after`` variants), advance to the
    opening ``{``, then walk forward tracking brace depth to find the
    matching ``}``.
    """
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"^void\s+par_insert_string\s*\(",
            text,
            re.MULTILINE,
        )
    )
    # Take the *last* definition: earlier matches may live inside the
    # function-pointer table or the documentation banner.
    assert matches, "par_insert_string definition not found"
    start = matches[-1].start()
    body_start = text.index("{", start)
    depth = 1
    i = body_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "par_insert_string body brace-matching failed"
    return text[body_start:i]


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    return [IndexData() for _ in range(n)]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_extract_body_reaches_end_of_function() -> None:
    """The brace-depth extractor returns a non-empty, balanced body."""
    body = _extract_body()
    assert body.startswith("{")
    assert body.endswith("}")
    # Sanity: the function returns void with no explicit ``return value;``
    # for the success path -- the trailing brace should be the last char.
    assert body.count("{") == body.count("}")


def test_german_compound_nouns_dispatches_on_after_flag() -> None:
    """The GERMAN_COMPOUND_NOUNS branch redirects to par_insert_string_after."""
    body = _extract_body()
    assert re.search(
        r"insert_operation_flags\s*&\s*BIN_AFTER_FLAG",
        body,
    )
    # The redirect call -- distinguished from par_insert_string_before by
    # the trailing ``_after(`` token boundary.
    assert re.search(r"\bpar_insert_string_after\s*\(", body)


def test_german_compound_nouns_dispatches_on_before_flag() -> None:
    """The GERMAN_COMPOUND_NOUNS branch redirects to par_insert_string_before."""
    body = _extract_body()
    assert re.search(
        r"insert_operation_flags\s*&\s*BIN_BEFORE_FLAG",
        body,
    )
    assert re.search(r"\bpar_insert_string_before\s*\(", body)


def test_calls_par_build_string_from_rule_with_bin_insert() -> None:
    """The interleave path materialises the insert via par_build_string_from_rule."""
    body = _extract_body()
    assert re.search(
        r"par_build_string_from_rule\s*\([^;]*BIN_INSERT",
        body,
    )


def test_new_length_formula() -> None:
    """``new_length = (output_offset - 1) * (length + 1) + 1``."""
    body = _extract_body()
    assert re.search(
        r"new_length\s*=\s*\(\s*ret_value\s*->\s*output_offset\s*-\s*1\s*\)"
        r"\s*\*\s*\(\s*length\s*\+\s*1\s*\)\s*\+\s*1",
        body,
    )


def test_reverse_interleave_loop_walks_pos_to_off() -> None:
    """The shift-and-insert loop walks from ``off`` down to ``pos``."""
    body = _extract_body()
    # while (pos<off) -- the reverse-copy loop guard.
    assert re.search(r"while\s*\(\s*pos\s*<\s*off\s*\)", body)
    # off-- is the in-loop decrement that walks the source pointer backward.
    assert re.search(r"\boff\s*--", body)
    # new_loc decreases by length each iteration to make room for the insert.
    assert re.search(r"new_loc\s*-=\s*length", body)
    # new_loc-- after the memcpy advances past the just-copied original char.
    assert re.search(r"new_loc\s*--", body)


def test_par_max_output_array_used_as_trash_index_slot() -> None:
    """Index markers move to PAR_MAX_OUTPUT_ARRAY-1 as the trash slot."""
    body = _extract_body()
    assert re.search(r"PAR_MAX_OUTPUT_ARRAY\s*-\s*1", body)


def test_memcpy_target_is_buf_into_output_array() -> None:
    """``memcpy(output_array + new_loc, buf, length)`` performs the in-place insert."""
    body = _extract_body()
    assert re.search(
        r"memcpy\s*\(\s*output_array\s*\+\s*new_loc\s*,\s*buf\s*,\s*length\s*\)",
        body,
    )


def test_output_offset_set_to_new_length() -> None:
    """The trailing assignment sets ``ret_value->output_offset = new_length``."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*output_offset\s*=\s*new_length",
        body,
    )


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def _make_simple_insert_rule(opcode: int, literal: bytes) -> bytes:
    """Build a one-action rule whose insert body is ``BIN_EXACT`` of ``literal``.

    Layout:

    .. code-block:: text

        [0] opcode (BIN_INSERT / BIN_AFTER / BIN_BEFORE)
        [1] _
        [2] end_of_action (last byte index consumed by the build loop)
        [3] _
        [4] BIN_EXACT
        [5] len(literal)
        [6..] literal bytes
    """
    rule = bytearray(20)
    rule[0] = opcode
    rule[4] = BIN_EXACT
    rule[5] = len(literal)
    rule[6 : 6 + len(literal)] = literal
    rule[2] = 5 + len(literal)
    return bytes(rule)


def test_plain_interleave_path_inserts_between_characters() -> None:
    """No-flag path: build 'X' via BIN_EXACT, interleave into 'AB'.

    With output_pos=0, output_offset=2, length=1, the new length is
    ``(2-1)*(1+1)+1 = 3`` and the resulting span is ``A X B``.
    """
    rule = _make_simple_insert_rule(0x1A, b"X")  # 0x1A == BIN_INSERT
    out = bytearray(b"AB" + b"\x00" * 100)
    ret = ReturnValue(output_pos=0, output_offset=2, rule=4)
    par_insert_string(
        rule,
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
        0,  # insert_operation_flags: neither AFTER nor BEFORE
    )
    assert bytes(out[:3]) == b"AXB"
    assert ret.output_offset == 3
    # Success path must not leave FATAL_FAIL behind.
    assert ret.value != FATAL_FAIL


def test_plain_interleave_three_char_span() -> None:
    """Interleave '-' between 'ABC' -> 'A-B-C', mirroring the doc example."""
    rule = _make_simple_insert_rule(0x1A, b"-")
    out = bytearray(b"ABC" + b"\x00" * 100)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string(
        rule,
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
    assert bytes(out[:5]) == b"A-B-C"
    # new_length = (3-1)*(1+1)+1 = 5.
    assert ret.output_offset == 5
    assert ret.value != FATAL_FAIL


def test_plain_interleave_multibyte_insert() -> None:
    """Multi-byte insert: 'XY' between 'ABCD' -> 'AXYBXYCXYD'."""
    rule = _make_simple_insert_rule(0x1A, b"XY")
    out = bytearray(b"ABCD" + b"\x00" * 100)
    ret = ReturnValue(output_pos=0, output_offset=4, rule=4)
    par_insert_string(
        rule,
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
    # new_length = (4-1)*(2+1)+1 = 10.
    assert ret.output_offset == 10
    assert bytes(out[:10]) == b"AXYBXYCXYD"
    assert ret.value != FATAL_FAIL


def test_after_flag_delegates_to_after_variant() -> None:
    """``BIN_AFTER_FLAG`` set -> delegates to par_insert_string_after."""
    rule = _make_simple_insert_rule(0x1B, b"X")  # 0x1B == BIN_AFTER
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string(
        rule,
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
        BIN_AFTER_FLAG,
    )
    # par_insert_string_after appends 'X' after the 'ABC' span and grows
    # output_offset by length(1) -> 4.
    assert bytes(out[:4]) == b"ABCX"
    assert ret.output_offset == 4
    assert ret.value != FATAL_FAIL


def test_before_flag_delegates_to_before_variant() -> None:
    """``BIN_BEFORE_FLAG`` set -> delegates to par_insert_string_before."""
    rule = _make_simple_insert_rule(0x1C, b"X")  # 0x1C == BIN_BEFORE
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string(
        rule,
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
        BIN_BEFORE_FLAG,
    )
    # par_insert_string_before prepends 'X' before the 'ABC' span and grows
    # output_offset by length(1) -> 4.
    assert bytes(out[:4]) == b"XABC"
    assert ret.output_offset == 4
    assert ret.value != FATAL_FAIL


def test_after_flag_takes_precedence_when_both_set() -> None:
    """When both AFTER and BEFORE bits are set, AFTER wins (it's checked first).

    Mirrors the C source order:

    .. code-block:: c

        if (insert_operation_flags & BIN_AFTER_FLAG) { ...; return; }
        if (insert_operation_flags & BIN_BEFORE_FLAG) { ...; return; }
    """
    rule = _make_simple_insert_rule(0x1B, b"Y")
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string(
        rule,
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
        BIN_AFTER_FLAG | BIN_BEFORE_FLAG,
    )
    # AFTER variant ran -> 'Y' is appended after 'ABC'.
    assert bytes(out[:4]) == b"ABCY"
    assert ret.output_offset == 4
    assert ret.value != FATAL_FAIL
