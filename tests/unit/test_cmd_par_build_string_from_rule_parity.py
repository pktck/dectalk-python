"""C-source parity test for ``par_build_string_from_rule`` against par_pars1.c.

Re-parses the C function body and asserts structural patterns from
the source — the signature, conditional-replace dispatch, and the
per-opcode build-loop — match the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_AFTER_FLAG,
    BIN_BEFORE_FLAG,
    BIN_CONDITIONAL_REPLACE,
    BIN_END_OF_RULE,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_INSERT,
    BIN_REPLACE,
    BIN_RESTORE,
)
from dectalk.cmd.par_build_string_from_rule import par_build_string_from_rule
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    match = re.search(
        r"unsigned\s+char\s*\*\s*par_build_string_from_rule\s*\([^)]*\)\s*\n\{(.+?)\nunsigned\s+char\s*\*\s*par_build_string_from_rule",
        text + "\nunsigned char *par_build_string_from_rule",
        re.DOTALL,
    )
    assert match is not None, "par_build_string_from_rule body not found"
    return match.group(1)


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_signature_matches() -> None:
    """The C signature carries the expected nine parameters."""
    text = _read_par_pars1_c()
    assert re.search(
        r"unsigned\s+char\s*\*\s*par_build_string_from_rule\s*\(\s*"
        r"unsigned\s+char\s*\*\s*current_rule\s*,\s*"
        r"unsigned\s+char\s*\*\s*buf\s*,\s*"
        r"unsigned\s+char\s*\*\s*output_array\s*,\s*"
        r"pmatch_arrays_t\s+match_array\s*,\s*"
        r"preturn_value_t\s+ret_value\s*,\s*"
        r"prange_value_t\s+range_value\s*,\s*"
        r"int\s+state\s*,\s*"
        r"int\s*\*\s*length\s*,\s*"
        r"int\s+in_rule_index\s*\)",
        text,
    )


def test_conditional_replace_gate() -> None:
    """The body gates the conditional path on BIN_CONDITIONAL_REPLACE."""
    body = _extract_body()
    assert "BIN_CONDITIONAL_REPLACE" in body
    assert re.search(
        r"current_rule\s*\[\s*in_rule_index\s*\]\s*&\s*BIN_CONDITIONAL_REPLACE",
        body,
    )


def test_german_compound_nouns_branch_in_source() -> None:
    """The active Linux branch keys the conditional switch on BIN_OPERATION_MASK."""
    body = _extract_body()
    # Inside the GERMAN_COMPOUND_NOUNS branch:
    assert "state & BIN_OPERATION_MASK" in body
    assert "BIN_INSERT" in body
    assert "BIN_BEFORE_FLAG" in body
    assert "BIN_AFTER_FLAG" in body


def test_build_loop_opcodes_present() -> None:
    """The build loop dispatches on BIN_EXACT / BIN_RESTORE / BIN_HEXADECIMAL."""
    body = _extract_body()
    assert "case BIN_EXACT" in body
    assert "case BIN_RESTORE" in body
    assert "case BIN_HEXADECIMAL" in body


def test_end_of_action_formula() -> None:
    """end_of_action = current_rule[in_rule_index + 2]."""
    body = _extract_body()
    assert re.search(
        r"end_of_action\s*=\s*current_rule\s*\[\s*in_rule_index\s*\+\s*2\s*\]",
        body,
    )


def test_ret_value_rule_advance_formula() -> None:
    """ret_value->rule = end_of_action + 1 on success."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*rule\s*=\s*end_of_action\s*\+\s*1",
        body,
    )


def test_par_convert_number_new2_used_for_default_branch() -> None:
    """The default branch uses par_convert_number_new2 to scan the output."""
    body = _extract_body()
    assert "par_convert_number_new2" in body


def test_fatal_fail_on_unrecognized_delimiter() -> None:
    """A bad opcode in the build loop sets value=FATAL_FAIL."""
    body = _extract_body()
    assert re.search(r"ret_value\s*->\s*value\s*=\s*FATAL_FAIL", body)


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def _make_rule_with_bin_exact(literal: bytes) -> bytes:
    """Build a rule with a single BIN_EXACT body of ``literal``."""
    # Header: [opcode][?][end_of_action][...]
    rule = bytearray(b"\x19\x00\x00\x00")  # BIN_REPLACE, _, end_of_action TBD, _
    rule.append(BIN_EXACT)
    rule.append(len(literal))
    rule.extend(literal)
    # end_of_action is the last byte the loop reads (rule_p stops at <= end).
    # rule_p walks 4 → BIN_EXACT, +1 → len, +1 → first char, +len-1 → last char.
    # The last position read by the loop is 5 + len(literal) - 1 = 4 + len + 1.
    rule[2] = 4 + 1 + len(literal)
    return bytes(rule)


def test_bin_exact_writes_literal_to_buf() -> None:
    """A BIN_EXACT body materialises its literal into ``buf``."""
    rule = _make_rule_with_bin_exact(b"hello")
    ret = ReturnValue(rule=4)
    buf = bytearray(20)
    length_box = [0]
    result = par_build_string_from_rule(
        rule,
        buf,
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert result is buf
    assert length_box[0] == 5
    assert bytes(buf[:5]) == b"hello"
    # ret.rule advances to end_of_action + 1.
    assert ret.rule == rule[2] + 1


def test_bin_restore_pulls_from_match_array() -> None:
    """A BIN_RESTORE body emits the bytes saved in ``match_array.array[N]``."""
    rule = bytearray(b"\x19\x00\x05\x00")  # header, end_of_action=5
    rule.append(BIN_RESTORE)
    rule.append(3)  # slot 3
    ret = ReturnValue(rule=4)
    buf = bytearray(20)
    ma = MatchArrays()
    ma.array_lengths[3] = 4
    ma.array[3][:4] = b"JOHN"
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        bytearray(50),
        ma,
        ret,
        RangeValue(),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert length_box[0] == 4
    assert bytes(buf[:4]) == b"JOHN"


def test_bin_hexadecimal_writes_single_byte() -> None:
    """A BIN_HEXADECIMAL body emits its single literal byte."""
    rule = bytearray(b"\x19\x00\x05\x00")
    rule.append(BIN_HEXADECIMAL)
    rule.append(0xAB)
    ret = ReturnValue(rule=4)
    buf = bytearray(20)
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert length_box[0] == 1
    assert buf[0] == 0xAB


def test_invalid_opcode_sets_fatal_fail() -> None:
    """A non-BIN_EXACT/RESTORE/HEXADECIMAL opcode triggers FATAL_FAIL."""
    rule = bytearray(b"\x19\x00\x05\x00")
    rule.append(0x05)  # BIN_CONSONANT — not allowed in the build loop
    rule.append(0)
    ret = ReturnValue(rule=4)
    result = par_build_string_from_rule(
        bytes(rule),
        bytearray(20),
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_REPLACE,
        [0],
        0,
    )
    assert result is None
    assert ret.value == FATAL_FAIL


def test_end_of_rule_state_sets_fatal_fail() -> None:
    """state == BIN_END_OF_RULE is a hard error per the SANITY_CHECKING block."""
    ret = ReturnValue()
    result = par_build_string_from_rule(
        b"\x19\x00\x05\x00",
        bytearray(20),
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_END_OF_RULE,
        [0],
        0,
    )
    assert result is None
    assert ret.value == FATAL_FAIL


def test_conditional_replace_range_set_2_uses_start() -> None:
    """range_set==2 → cond_num = range_value.start, picks that conditional body."""
    # 2 conditionals; cond_num=1 picks rule_p=rule[4]+1, end_of_build=rule[5].
    rule = bytearray(50)
    rule[0] = 0x19 | BIN_CONDITIONAL_REPLACE
    rule[2] = 30
    rule[3] = 2  # num_conds
    rule[4] = 10  # cond_0 end → cond_1 start at 11
    rule[5] = 15  # cond_1 end
    rule[11] = BIN_EXACT
    rule[12] = 3
    rule[13] = ord("X")
    rule[14] = ord("Y")
    rule[15] = ord("Z")
    ret = ReturnValue()
    buf = bytearray(20)
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        bytearray(b"X" * 50),
        MatchArrays(),
        ret,
        RangeValue(range_set=2, start=1),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert length_box[0] == 3
    assert bytes(buf[:3]) == b"XYZ"


def test_conditional_replace_before_flag_reads_first_char() -> None:
    """BIN_INSERT|BIN_BEFORE_FLAG: cond_num = output_array[output_pos] - '0'."""
    # output[0]='2' → cond_num=2, num_conds=2 → cond_num==num_conds path.
    rule = bytearray(50)
    rule[0] = 0x1A | BIN_CONDITIONAL_REPLACE
    rule[2] = 19  # end_of_action: last byte of cond_2 body
    rule[3] = 2  # num_conds
    rule[4] = 10  # cond_0 end
    rule[5] = 15  # cond_1 end
    # cond_2 starts at rule[3+2]+1 = rule[5]+1 = 16; end = rule[2] = 19.
    rule[16] = BIN_EXACT
    rule[17] = 2
    rule[18] = ord("!")
    rule[19] = ord("?")
    out = bytearray(b"2" + b"\x00" * 49)
    ret = ReturnValue(output_pos=0)
    buf = bytearray(20)
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        out,
        MatchArrays(),
        ret,
        RangeValue(range_set=0),
        BIN_INSERT | BIN_BEFORE_FLAG,
        length_box,
        0,
    )
    assert length_box[0] == 2
    assert bytes(buf[:2]) == b"!?"


def test_conditional_replace_after_flag_reads_last_char() -> None:
    """BIN_INSERT|BIN_AFTER_FLAG: cond_num = output_array[output_pos+output_offset-1]-'0'."""
    # 'A1' + '2' span: output[2]='2' → cond_num=2 → cond_2 (last) path.
    rule = bytearray(50)
    rule[0] = 0x1A | BIN_CONDITIONAL_REPLACE
    rule[2] = 18  # end_of_action: last byte of cond_2 body (rule[18])
    rule[3] = 2
    rule[4] = 10
    rule[5] = 15
    rule[16] = BIN_EXACT
    rule[17] = 1
    rule[18] = ord("Z")
    out = bytearray(b"A12" + b"\x00" * 50)
    ret = ReturnValue(output_pos=0, output_offset=3)
    buf = bytearray(20)
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        out,
        MatchArrays(),
        ret,
        RangeValue(range_set=0),
        BIN_INSERT | BIN_AFTER_FLAG,
        length_box,
        0,
    )
    assert length_box[0] == 1
    assert buf[0] == ord("Z")


def test_conditional_replace_zero_picks_default_body() -> None:
    """cond_num clamps to 0 when > num_conds, end_of_build = rule[in_rule_index+4]."""
    # num_conds=1, cond_num=5 (range_set=2,start=5) → clamps to 0.
    rule = bytearray(50)
    rule[0] = 0x19 | BIN_CONDITIONAL_REPLACE
    rule[2] = 20
    rule[3] = 1
    rule[4] = 9  # end_of_build for cond_0 (initial rule_p = ret_value.rule = 5)
    rule[5] = BIN_EXACT
    rule[6] = 3
    rule[7] = ord("A")
    rule[8] = ord("B")
    rule[9] = ord("C")
    ret = ReturnValue(rule=5)
    buf = bytearray(20)
    length_box = [0]
    par_build_string_from_rule(
        bytes(rule),
        buf,
        bytearray(b"X" * 50),
        MatchArrays(),
        ret,
        RangeValue(range_set=2, start=5),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert length_box[0] == 3
    assert bytes(buf[:3]) == b"ABC"


def test_length_out_parameter_set() -> None:
    """The ``length`` out-parameter receives the byte count written."""
    rule = _make_rule_with_bin_exact(b"hi")
    ret = ReturnValue(rule=4)
    buf = bytearray(20)
    length_box = [-1]
    par_build_string_from_rule(
        rule,
        buf,
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert length_box[0] == 2


def test_buf_nul_terminated_after_build() -> None:
    """``buf[length]`` is NUL-terminated after the build loop."""
    rule = _make_rule_with_bin_exact(b"hi")
    ret = ReturnValue(rule=4)
    buf = bytearray(20)
    for k in range(len(buf)):
        buf[k] = 0xFF  # poison
    length_box = [0]
    par_build_string_from_rule(
        rule,
        buf,
        bytearray(50),
        MatchArrays(),
        ret,
        RangeValue(),
        BIN_REPLACE,
        length_box,
        0,
    )
    assert buf[2] == 0
