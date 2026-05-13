"""C-source parity test for ``par_insert_string_after`` against par_pars1.c.

Re-parses the C function body with brace-depth tracking and asserts
structural patterns match the Python port:

- call to :func:`par_build_string_from_rule` with the combined
  ``BIN_INSERT | BIN_AFTER_FLAG`` opcode on the GERMAN_COMPOUND_NOUNS
  build (active on Linux), or the equivalent ``BIN_AFTER`` opcode
  on the legacy branch,
- placement of the materialised insert string AFTER
  ``output_pos + output_offset``,
- the ``output_indexes`` invariant: the function relies on
  ``copy_string_data`` to have already copied them through, so no
  index work happens in the body.

Behavioural tests then exercise the Python port and verify the
inserted bytes land at the expected indices, ``output_offset`` grows
by the insert length, and ``ret_value.value`` is not set to
:data:`FATAL_FAIL` on the success path.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_EXACT
from dectalk.cmd.par_insert_string_after import par_insert_string_after
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


def _skip_ws_and_preproc(text: str, i: int) -> int:
    """Advance ``i`` past whitespace and ``#...\\n`` preprocessor lines."""
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "#":
            # Skip to end of line (preprocessor directives are single line
            # for our purposes — no continuation backslashes are in play here).
            nl = text.find("\n", i)
            if nl < 0:
                return len(text)
            i = nl + 1
        else:
            break
    return i


def _find_body_start(text: str, sig_end: int) -> int:
    """Walk past a parameter list and return the index just after ``{``.

    Returns ``-1`` if the candidate signature at ``sig_end`` belongs to a
    forward declaration (``);``) rather than a definition (``) {``).

    Because the parameter list straddles an ``#ifndef GERMAN_COMPOUND_NOUNS``
    block, there are TWO ``)`` characters that close paren depth to zero —
    one per ``#if/#else`` branch — so we peek the next non-whitespace,
    non-preprocessor character after every such ``)``.
    """
    i = sig_end
    paren_depth = 1
    while i < len(text) and paren_depth > 0:
        ch = text[i]
        i += 1
        if ch == "(":
            paren_depth += 1
            continue
        if ch != ")":
            continue
        paren_depth -= 1
        if paren_depth != 0:
            continue
        nxt = _skip_ws_and_preproc(text, i)
        if nxt >= len(text):
            return -1
        peek = text[nxt]
        if peek == "{":
            return nxt + 1
        if peek == ";":
            return -1
        # Between #if/#else branches — keep scanning for the other ')'.
        paren_depth = 1
    return -1


def _find_brace_end(text: str, body_start: int) -> int:
    """Return the index of the closing ``}`` matching ``body_start - 1``."""
    depth = 1
    j = body_start
    while j < len(text) and depth > 0:
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        j += 1
    assert depth == 0, "unbalanced braces"
    return j - 1


def _extract_body() -> str:
    """Return the body of ``par_insert_string_after`` using brace-depth tracking.

    The file contains both a forward declaration (terminated by ``;``)
    and the definition (terminated by ``{ ... }``), and the parameter
    list of each spans an ``#ifndef GERMAN_COMPOUND_NOUNS`` block — so
    a naive ``(.+?)\\{`` regex would either lock onto the prototype's
    trailing ``;`` or sail past the function-opening ``{``. We scan
    each candidate signature with :func:`_find_body_start`, which
    handles paren depth and the preprocessor branching, and stop at
    the first match that returns a real body. The body is then sliced
    via :func:`_find_brace_end`.
    """
    text = _read_par_pars1_c()
    for match in re.finditer(
        r"^void\s+par_insert_string_after\s*\(",
        text,
        re.MULTILINE,
    ):
        body_start = _find_body_start(text, match.end())
        if body_start >= 0:
            brace_end = _find_brace_end(text, body_start)
            return text[body_start:brace_end]
    raise AssertionError("definition of par_insert_string_after not found")


def _empty_indexes(n: int = PAR_MAX_OUTPUT_ARRAY) -> list[IndexData]:
    return [IndexData() for _ in range(n)]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_present() -> None:
    """The C signature for ``par_insert_string_after`` exists in par_pars1.c."""
    text = _read_par_pars1_c()
    assert re.search(
        r"void\s+par_insert_string_after\s*\(\s*"
        r"unsigned\s+char\s*\*\s*current_rule",
        text,
    )


def test_calls_par_build_string_from_rule() -> None:
    """The body delegates to ``par_build_string_from_rule`` for the insert opcode."""
    body = _extract_body()
    assert "par_build_string_from_rule" in body
    # The build call passes &length and in_rule_index as the trailing args.
    assert re.search(
        r"par_build_string_from_rule\s*\([^;]*&\s*length\s*,\s*in_rule_index\s*\)",
        body,
    )


def test_build_call_uses_bin_after_opcode() -> None:
    """The build call uses ``BIN_INSERT | BIN_AFTER_FLAG`` (or ``BIN_AFTER``).

    Both branches appear in the body: the legacy ``#ifndef
    GERMAN_COMPOUND_NOUNS`` path uses ``BIN_AFTER`` and the active
    Linux ``#else`` path uses ``BIN_INSERT | BIN_AFTER_FLAG``. We
    require at least one of them to appear.
    """
    body = _extract_body()
    legacy = re.search(r"\bBIN_AFTER\b(?!\s*_FLAG)", body) is not None
    german = re.search(r"\bBIN_INSERT\s*\|\s*BIN_AFTER_FLAG\b", body) is not None
    assert legacy or german, "no BIN_AFTER or BIN_INSERT|BIN_AFTER_FLAG opcode in build call"
    # The Linux build (which we test against) takes the German branch.
    assert german, "BIN_INSERT|BIN_AFTER_FLAG opcode not present in body"


def test_append_destination_is_after_output_pos_plus_offset() -> None:
    """The strcpy / memcpy destination is ``output_pos + output_offset``."""
    body = _extract_body()
    # strcpy(output_array + (ret_value->output_pos + ret_value->output_offset), buf)
    assert re.search(
        r"strcpy\s*\(\s*\(?\s*output_array\s*\+\s*\(?\s*"
        r"ret_value\s*->\s*output_pos\s*\+\s*ret_value\s*->\s*output_offset",
        body,
    ), "strcpy destination is not output_pos + output_offset"
    # memcpy(output_array + (ret_value->output_pos + ret_value->output_offset), buf, length)
    assert re.search(
        r"memcpy\s*\(\s*\(?\s*output_array\s*\+\s*\(?\s*"
        r"ret_value\s*->\s*output_pos\s*\+\s*ret_value\s*->\s*output_offset"
        r"[^,]*,\s*buf\s*,\s*length\s*\)",
        body,
    ), "memcpy destination/length not at output_pos + output_offset for `length` bytes"


def test_output_offset_grows_by_length() -> None:
    """``output_offset += length`` finalises the inserted span."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*output_offset\s*\+=\s*length",
        body,
    )


def test_output_indexes_relies_on_copy_string_data() -> None:
    """``output_indexes`` are not rewritten here.

    The C body's only mention of indexes is a comment confirming
    ``copy_string_data`` already placed them; there is no index
    write in this function. We assert the comment is present, which
    pins the contract for the Python port.
    """
    body = _extract_body()
    # The comment in the C source: "the indexes will have been
    # copied by copy_string _data" (sic). We accept either spelling
    # of "copy_string_data" with or without the rogue space.
    assert re.search(r"indexes\s+will\s+have\s+been\s+copied\s+by\s+copy_string", body), (
        "expected the 'indexes have been copied by copy_string_data' contract comment"
    )
    # And there are no writes of the form ``output_indexes[...] = ...``
    # nor ``output_indexes->`` field assignments in the body.
    assert not re.search(r"output_indexes\s*\[[^\]]*\]\s*[.=]", body), (
        "unexpected output_indexes index write inside par_insert_string_after"
    )
    assert not re.search(r"output_indexes\s*->", body), (
        "unexpected output_indexes pointer write inside par_insert_string_after"
    )


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_inserts_two_chars_after_three_char_span() -> None:
    """A 2-char built string is inserted after a 3-char span at indices 3..4."""
    # Rule: BIN_AFTER (0x1B) opcode header, BIN_EXACT body of "XY".
    #
    #   rule[0] = 0x1B            opcode
    #   rule[2] = 7               end_of_action (last byte of literal)
    #   rule[4] = BIN_EXACT
    #   rule[5] = 2               length
    #   rule[6..7] = "XY"
    rule = bytearray(20)
    rule[0] = 0x1B  # BIN_AFTER
    rule[2] = 7
    rule[4] = BIN_EXACT
    rule[5] = 2
    rule[6] = ord("X")
    rule[7] = ord("Y")
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string_after(
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
    # Inserted bytes land at indices 3 and 4 (after the 3-char span).
    assert out[3] == ord("X")
    assert out[4] == ord("Y")
    # The 3-char span itself is untouched.
    assert bytes(out[:3]) == b"ABC"
    # And success: value is NOT FATAL_FAIL.
    assert ret.value != FATAL_FAIL


def test_output_offset_incremented_by_insert_length() -> None:
    """``ret_value.output_offset`` grows by the length of the inserted string."""
    # 2-char built string, starting offset 3 → final offset 5.
    rule = bytearray(20)
    rule[0] = 0x1B
    rule[2] = 7
    rule[4] = BIN_EXACT
    rule[5] = 2
    rule[6] = ord("X")
    rule[7] = ord("Y")
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    par_insert_string_after(
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
    assert ret.output_offset == 3 + 2


def test_success_path_does_not_set_fatal_fail() -> None:
    """On a well-formed rule, ``ret_value.value`` is not :data:`FATAL_FAIL`."""
    rule = bytearray(20)
    rule[0] = 0x1B
    rule[2] = 7
    rule[4] = BIN_EXACT
    rule[5] = 2
    rule[6] = ord("a")
    rule[7] = ord("b")
    out = bytearray(b"ABC" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3, rule=4)
    # Pre-seed with FATAL_FAIL would be a tampering — leave default 0.
    par_insert_string_after(
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
