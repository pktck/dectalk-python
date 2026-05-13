"""C-source parity test for ``par_dom_dict_search`` against par_pars1.c.

Re-parses the C function body via manual brace-depth tracking
(the standard ``[^;{]+?`` parameter-block regex won't work
because the signature is split across an
``#ifndef GERMAN_COMPOUND_NOUNS`` / ``#else`` / ``#endif``
block) and asserts the dispatch shape — bounds-check, scratch
slot writes, ``par_search_for_word`` call and the
``BIN_DICT_HIT_FAIL`` / ``BIN_DICT_MISS_FAIL`` branches — is
preserved by the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_DICT_HIT_FAIL, BIN_DICT_MISS_FAIL
from dectalk.cmd.par_dom_dict_search import par_dom_dict_search
from dectalk.cmd.par_structs import (
    PAR_MAX_MATCH_ARRAY,
    IndexData,
    MatchArrays,
    RangeValue,
    ReturnValue,
)
from dectalk.cmd.rule_states import FAIL, FATAL_FAIL, OPT_FAIL, SUCCESS

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _skip_ws_and_directives(text: str, i: int) -> int:
    """Advance past whitespace and ``#ifdef`` / ``#else`` / ``#endif`` directives."""
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "#":
            # Skip the rest of the preprocessor directive line.
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        break
    return i


def _extract_body() -> str:  # noqa: PLR0912 — paren-balancing across #ifdef arms
    """Walk text manually — the signature spans an ``#ifndef`` block.

    The C file has the function declared once (around line 553, ending
    in ``;`` inside an ``#ifndef`` block) and defined once (around line
    3481, body in braces, with the same preprocessor block bracketing
    the final parameter). The standard ``[^;{]+?`` parameter-block
    regex won't work because the parameter list straddles
    ``#ifndef`` / ``#else`` / ``#endif`` directives — each variant
    closes its own ``)``. We pick the variant that the Linux build
    sees (``GERMAN_COMPOUND_NOUNS`` defined → the ``#else`` branch)
    and balance-paren over the entire macro block, then look for the
    body brace beyond the trailing ``#endif`` / whitespace.
    """
    text = _read_par_pars1_c()
    starts = [
        m.start()
        for m in re.finditer(r"\bvoid\s+par_dom_dict_search\s*\(", text)
    ]
    assert starts, "par_dom_dict_search definition not found"
    for start in starts:
        i = text.index("(", start)
        depth = 1
        i += 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "#":
                # Skip the entire preprocessor directive line — its
                # parens (if any) belong to a conditional alternative
                # we already chose past or before.
                while i < len(text) and text[i] != "\n":
                    i += 1
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    # Could be the ``#ifndef`` arm's ``)``. Peek past
                    # whitespace / directives: if the next non-skipped
                    # char is another ``)`` (impossible here) or an
                    # identifier starting a new param block, we'd keep
                    # going. In practice the trailing ``#endif`` is
                    # followed by either ``{`` (definition) or ``;``
                    # (forward decl). If it's neither, this is the
                    # ``#ifndef`` arm and we should resume from after
                    # the matching ``#endif``.
                    nxt = _skip_ws_and_directives(text, i + 1)
                    if nxt < len(text) and text[nxt] in "{;":
                        i += 1
                        break
                    # Restart the balanced scan from the alternative
                    # parameter list inside ``#else``.
                    depth = 1
            i += 1
        if depth != 0:
            continue
        j = _skip_ws_and_directives(text, i)
        if j >= len(text) or text[j] != "{":
            continue
        body_start = j
        depth = 1
        i = body_start + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start:i]
    raise AssertionError("par_dom_dict_search body not found")


# -- Structural assertions --------------------------------------------------


def test_calls_par_search_for_word_with_slot8() -> None:
    """The C body calls ``par_search_for_word(match_array->array[8], ...)``."""
    body = _extract_body()
    assert re.search(
        r"par_search_for_word\s*\(\s*match_array\s*->\s*array\s*\[\s*8\s*\]\s*,",
        body,
    )


def test_passes_output_offset_and_slot9() -> None:
    """par_search_for_word's 2nd / 3rd args are output_offset and slot 9."""
    body = _extract_body()
    assert re.search(
        r"par_search_for_word\s*\(\s*match_array\s*->\s*array\s*\[\s*8\s*\]\s*,\s*"
        r"ret_value\s*->\s*output_offset\s*,\s*"
        r"match_array\s*->\s*array\s*\[\s*9\s*\]",
        body,
    )


def test_sets_array_lengths_7() -> None:
    """The body sets ``match_array->array_lengths[7] = input_offset``."""
    body = _extract_body()
    assert re.search(
        r"match_array\s*->\s*array_lengths\s*\[\s*7\s*\]\s*=\s*ret_value\s*->\s*input_offset",
        body,
    )


def test_sets_array_lengths_8() -> None:
    """The body sets ``match_array->array_lengths[8] = output_offset``."""
    body = _extract_body()
    assert re.search(
        r"match_array\s*->\s*array_lengths\s*\[\s*8\s*\]\s*=\s*ret_value\s*->\s*output_offset",
        body,
    )


def test_reads_bin_dict_hit_fail() -> None:
    """The body tests ``current_rule[in_rule_index] & BIN_DICT_HIT_FAIL``."""
    body = _extract_body()
    assert re.search(
        r"current_rule\s*\[\s*in_rule_index\s*\]\s*&\s*BIN_DICT_HIT_FAIL",
        body,
    )


def test_reads_bin_dict_miss_fail() -> None:
    """The miss branch tests ``current_rule[in_rule_index] & BIN_DICT_MISS_FAIL``."""
    body = _extract_body()
    assert re.search(
        r"current_rule\s*\[\s*in_rule_index\s*\]\s*&\s*BIN_DICT_MISS_FAIL",
        body,
    )


def test_dispatches_on_result_equals_one() -> None:
    """The dispatch is split on ``if (result==1)`` vs the else branch."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*result\s*==\s*1\s*\)", body)


def test_fatal_fail_on_input_overflow() -> None:
    """The first guard FATAL_FAILs when ``input_offset >= PAR_MAX_MATCH_ARRAY``."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*input_offset\s*>=\s*PAR_MAX_MATCH_ARRAY",
        body,
    )
    assert re.search(r"ret_value\s*->\s*value\s*=\s*FATAL_FAIL", body)


def test_fatal_fail_on_output_overflow() -> None:
    """The second guard FATAL_FAILs when ``output_offset >= PAR_MAX_MATCH_ARRAY``."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*output_offset\s*>=\s*PAR_MAX_MATCH_ARRAY",
        body,
    )


def test_dict_state_flag_short_circuit() -> None:
    """``if (dict_state_flag)`` block returns early on hit/miss."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*dict_state_flag\s*\)", body)


def test_opt_fail_branch_on_optional() -> None:
    """The fail branches honour ``ret_value->optional == 1`` -> ``OPT_FAIL``."""
    body = _extract_body()
    assert re.search(r"ret_value\s*->\s*optional\s*==\s*1", body)
    assert re.search(r"ret_value\s*->\s*value\s*=\s*OPT_FAIL", body)


# -- Behavioural tests ------------------------------------------------------


def _make_state(
    *,
    input_pos: int = 0,
    output_pos: int = 0,
    input_offset: int = 0,
    output_offset: int = 0,
    optional: int = 0,
) -> ReturnValue:
    return ReturnValue(
        input_pos=input_pos,
        output_pos=output_pos,
        input_offset=input_offset,
        output_offset=output_offset,
        optional=optional,
    )


def _call(
    current_rule: bytes,
    input_array: bytearray,
    output_array: bytearray,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    *,
    dict_num: int = 1,
    dict_state_flag: int = 0,
    in_rule_index: int = 0,
    insert_operation_flags: int = 0,
) -> None:
    par_dom_dict_search(
        current_rule,
        input_array,
        output_array,
        [IndexData() for _ in range(3)],
        [IndexData() for _ in range(3)],
        match_array,
        ret_value,
        RangeValue(),
        dict_num,
        dict_state_flag,
        in_rule_index,
        insert_operation_flags,
    )


def test_fatal_fail_when_input_offset_overflows() -> None:
    """``input_offset == PAR_MAX_MATCH_ARRAY`` -> ``value = FATAL_FAIL``."""
    ret = _make_state(input_offset=PAR_MAX_MATCH_ARRAY, output_offset=1)
    _call(
        b"\x00" * 8,
        bytearray(b"abc"),
        bytearray(b"xyz"),
        MatchArrays(),
        ret,
    )
    assert ret.value == FATAL_FAIL


def test_fatal_fail_when_output_offset_overflows() -> None:
    """``output_offset == PAR_MAX_MATCH_ARRAY`` -> ``value = FATAL_FAIL``."""
    ret = _make_state(input_offset=1, output_offset=PAR_MAX_MATCH_ARRAY)
    _call(
        b"\x00" * 8,
        bytearray(b"abc"),
        bytearray(b"xyz"),
        MatchArrays(),
        ret,
    )
    assert ret.value == FATAL_FAIL


def test_copies_input_span_into_slot7() -> None:
    """``match_array.array[7][:input_offset]`` mirrors ``input_array[ipos:ipos+input_offset]``."""
    ret = _make_state(input_pos=1, output_pos=2, input_offset=3, output_offset=2)
    ma = MatchArrays()
    _call(
        b"\x00" * 8,
        bytearray(b"_abcd_"),
        bytearray(b"__yz_"),
        ma,
        ret,
    )
    assert bytes(ma.array[7][:3]) == b"abc"
    assert ma.array[7][3] == 0  # trailing NUL
    assert ma.array_lengths[7] == 3


def test_copies_output_span_into_slot8() -> None:
    """``match_array.array[8][:offset]`` mirrors ``output_array[opos:opos+offset]``."""
    ret = _make_state(input_pos=0, output_pos=1, input_offset=2, output_offset=4)
    ma = MatchArrays()
    _call(
        b"\x00" * 8,
        bytearray(b"abXY"),
        bytearray(b"_WXYZ"),
        ma,
        ret,
    )
    assert bytes(ma.array[8][:4]) == b"WXYZ"
    assert ma.array[8][4] == 0
    assert ma.array_lengths[8] == 4


def test_dict_state_flag_miss_returns_without_setting_value() -> None:
    """With ``dict_state_flag=1`` and a miss, value stays at its prior state."""
    # Stub par_search_for_word always returns 0 (miss).
    ret = _make_state(input_offset=1, output_offset=1)
    ret.value = SUCCESS  # prior state to verify it isn't overwritten on the miss path
    _call(
        b"\x00" * 8,
        bytearray(b"a"),
        bytearray(b"x"),
        MatchArrays(),
        ret,
        dict_state_flag=1,
    )
    # Miss + short-search: the C path falls through to the bare
    # ``return;`` and leaves value untouched.
    assert ret.value == SUCCESS


def test_dict_state_flag_zero_miss_advances_rule_to_miss_block() -> None:
    """``dict_state_flag=0`` + miss + no MISS_FAIL flag → ``rule = current_rule[idx+3]+1``."""
    # Rule byte 0 = no flags. Byte at +3 = 42. Pre-seed ret.value with a
    # sentinel so we can verify it is *not* overwritten by the FAIL path.
    rule = bytes([0x00, 0xAA, 0xBB, 0x2A, 0xCC])
    sentinel = 99
    ret = _make_state(input_offset=1, output_offset=1)
    ret.value = sentinel
    _call(
        rule,
        bytearray(b"a"),
        bytearray(b"x"),
        MatchArrays(),
        ret,
        in_rule_index=0,
    )
    # par_search_for_word stub returns 0 → miss branch.
    # Rule byte 0 has no BIN_DICT_MISS_FAIL → falls through and sets
    # ``rule = current_rule[in_rule_index+3] + 1`` = 0x2A + 1.
    assert ret.rule == 0x2B
    # No FAIL because the MISS_FAIL bit is clear — sentinel preserved.
    assert ret.value == sentinel
    # Cursors are reset for rematching.
    assert ret.input_offset == 0
    assert ret.output_offset == 0


def test_miss_with_bin_dict_miss_fail_sets_fail() -> None:
    """Miss + ``BIN_DICT_MISS_FAIL`` flag → ``value = FAIL``."""
    rule = bytes([BIN_DICT_MISS_FAIL, 0, 0, 7, 0])
    ret = _make_state(input_offset=1, output_offset=1)
    _call(
        rule,
        bytearray(b"a"),
        bytearray(b"x"),
        MatchArrays(),
        ret,
    )
    assert ret.value == FAIL


def test_miss_fail_with_optional_one_sets_opt_fail() -> None:
    """Miss + MISS_FAIL + ``optional == 1`` → ``value = OPT_FAIL``."""
    rule = bytes([BIN_DICT_MISS_FAIL, 0, 0, 7, 0])
    ret = _make_state(input_offset=1, output_offset=1, optional=1)
    _call(
        rule,
        bytearray(b"a"),
        bytearray(b"x"),
        MatchArrays(),
        ret,
    )
    assert ret.value == OPT_FAIL


def test_hit_with_bin_dict_hit_fail_sets_fail() -> None:
    """Hit + ``BIN_DICT_HIT_FAIL`` flag would set ``value = FAIL``.

    The Python stub for :func:`par_search_for_word` always returns 0,
    so we can't directly exercise the hit branch behaviourally. The
    structural test (``test_reads_bin_dict_hit_fail``) covers the
    presence of that branch in the C source. Here we verify the dual
    case: when ``BIN_DICT_HIT_FAIL`` is set but the stub reports a
    miss, the dispatch still uses the miss path (which doesn't read
    HIT_FAIL) and advances the rule cursor as expected.
    """
    # Byte at +3 = 5 → expected rule = 6 after the miss branch.
    rule = bytes([BIN_DICT_HIT_FAIL, 0, 0, 5, 0])
    sentinel = 77
    ret = _make_state(input_offset=1, output_offset=1)
    ret.value = sentinel
    _call(
        rule,
        bytearray(b"a"),
        bytearray(b"x"),
        MatchArrays(),
        ret,
    )
    # Stub miss + no MISS_FAIL bit → falls through, sentinel intact.
    assert ret.value == sentinel
    assert ret.rule == 6
