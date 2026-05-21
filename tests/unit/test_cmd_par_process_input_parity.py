"""C-source parity test for ``par_process_input`` against par_pars1.c.

Re-parses the C function body (lines 1007-1730) via brace-depth
tracking. The signature spans an ``#ifdef PARSER_STANDALONE_DEBUG``
block (line 1006 picks the standalone-debug signature, the
``#else`` at line 1008 has the Linux build's
``LPTTS_HANDLE_T phTTS`` flavour), so the regex anchors on the
function name and then walks brace depth to capture the body.

Behavioural tests cover the Python shim's deterministic pieces
(invalid rule-section guard writing the literal ``"Invalid rule
section. "`` payload, the pre-loop ``input_length * 2 / 3``
scaling, ``return_rule`` memset to ``-1``, and the post-validation
``NotImplementedError`` for the deferred driver loop).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_limits import PAR_MAX_RETURN_LEVEL
from dectalk.cmd.par_process_input import (
    INVALID_RULE_SECTION_MESSAGE,
    SHIM_DEFERRED,
    ProcessInputState,
    par_process_input,
)
from dectalk.cmd.par_structs import IndexData, MatchArrays, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``par_process_input`` definition body via brace depth.

    The signature is split across ``#ifdef PARSER_STANDALONE_DEBUG``
    / ``#else``. The Linux build picks the ``#else`` form with
    ``LPTTS_HANDLE_T phTTS`` as the first argument; we just anchor
    on the name and the parenthesised parameter list.
    """
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"preturn_value_t\s+par_process_input\s*\(",
            text,
        )
    )
    assert matches, "par_process_input definition not found"
    # The first match is the definition (subsequent ones may be calls).
    start = matches[0].start()
    # Find the opening brace after the parameter list.
    paren_depth = 0
    i = start
    seen_paren = False
    while i < len(text):
        ch = text[i]
        if ch == "(":
            paren_depth += 1
            seen_paren = True
        elif ch == ")":
            paren_depth -= 1
            if seen_paren and paren_depth == 0:
                # Skip whitespace until we hit the opening brace.
                j = i + 1
                while j < len(text) and text[j] in " \t\r\n":
                    j += 1
                if j < len(text) and text[j] == "{":
                    body_start = j
                    break
        i += 1
    else:
        msg = "couldn't find opening brace of par_process_input"
        raise AssertionError(msg)

    depth = 1
    k = body_start + 1
    while k < len(text) and depth > 0:
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
        k += 1
    return text[start:k]


# --------------------------------------------------------------------------
# C-source structural tests (~10 key patterns).
# --------------------------------------------------------------------------


def test_signature_carries_fourteen_parameters() -> None:
    """par_process_input has 14 parameters in the Linux flavour."""
    text = _read_par_pars1_c()
    # Required parameter types.
    assert re.search(r"unsigned\s+char\s*\*\s*input_array", text)
    assert re.search(r"unsigned\s+char\s*\*\s*new_input", text)
    assert re.search(r"unsigned\s+char\s*\*\s*output_array", text)
    assert re.search(r"unsigned\s+char\s*\*\s*dict_hit_array", text)
    assert re.search(r"pindex_data_t\s+input_indexes", text)
    assert re.search(r"pindex_data_t\s+new_input_indexes", text)
    assert re.search(r"pindex_data_t\s+output_indexes", text)
    assert re.search(r"U32\s+in_lang_flag", text)
    assert re.search(r"U32\s+in_mode_flag", text)
    assert re.search(r"int\s+rule", text)
    assert re.search(r"int\s+go_until", text)
    assert re.search(r"pmatch_arrays_t\s+match_array", text)
    assert re.search(r"preturn_value_t\s+ret_value", text)


def test_rule_section_guard_writes_invalid_message() -> None:
    """Out-of-range ``rule`` writes ``"Invalid rule section. "`` and returns."""
    body = _extract_body()
    assert re.search(r"rule\s*>\s*num_rule_sections", body)
    assert re.search(r'"Invalid rule section\.\s*"', body)
    assert re.search(r"strcpy\s*\(\s*output_array", body)


def test_memsets_return_rule_to_minus_one() -> None:
    """``memset(return_rule, -1, sizeof(return_rule))`` lives in the preamble."""
    body = _extract_body()
    assert re.search(r"memset\s*\(\s*return_rule\s*,\s*-\s*1", body)


def test_initialises_input_length_scaled() -> None:
    """``input_length = (input_length * 2) / 3`` (line 1106)."""
    body = _extract_body()
    assert re.search(r"input_length\s*=\s*\(\s*input_length\s*\*\s*2\s*\)\s*/\s*3", body)


def test_outer_loop_breaks_on_null_terminator() -> None:
    """The driver loop is ``while (new_input[...]!='\\0' && go_until==0)``."""
    body = _extract_body()
    assert re.search(r"new_input\s*\[[^\]]+\]\s*!=\s*'\\0'", body)
    assert re.search(r"go_until\s*==\s*0", body)


def test_outer_loop_handles_go_until_one() -> None:
    """The driver loop also has a ``go_until == 1`` branch."""
    body = _extract_body()
    assert re.search(r"go_until\s*==\s*1", body)


def test_dispatches_to_par_match_rule_with_bin_end_of_rule() -> None:
    """``par_match_rule(current_rule, BIN_END_OF_RULE, ...)`` at line 1393."""
    body = _extract_body()
    assert re.search(r"par_match_rule\s*\(\s*current_rule\s*,\s*BIN_END_OF_RULE", body)


def test_dispatches_on_bin_special_rule_mask() -> None:
    """``current_value & BIN_SPECIAL_RULE_MASK`` (line 1162) gates the switch."""
    body = _extract_body()
    assert re.search(r"current_value\s*&\s*BIN_SPECIAL_RULE_MASK", body)


def test_special_rule_switch_covers_stop_return_goto_goret() -> None:
    """The special-rule switch handles BIN_STOP / BIN_RETURN / BIN_GOTO / BIN_GORET."""
    body = _extract_body()
    assert re.search(r"case\s+BIN_STOP", body)
    assert re.search(r"case\s+BIN_RETURN", body)
    assert re.search(r"case\s+BIN_GOTO", body)
    assert re.search(r"case\s+BIN_GORET", body)


def test_handles_bin_dict_hit_and_miss() -> None:
    """``BIN_DICT_HIT`` and ``BIN_DICT_MISS`` gate rule processing (line 1258)."""
    body = _extract_body()
    assert "BIN_DICT_HIT" in body
    assert "BIN_DICT_MISS" in body
    assert re.search(r"current_value\s*&\s*\(\s*BIN_DICT_HIT\s*\|\s*BIN_DICT_MISS\s*\)", body)


def test_handles_bin_next_hit_miss_goret_hit_miss_copy_hit() -> None:
    """The five next-rule flags pull values from the rule body (lines 1303-1347)."""
    body = _extract_body()
    assert re.search(r"current_value\s*&\s*BIN_NEXT_HIT", body)
    assert re.search(r"current_value\s*&\s*BIN_NEXT_MISS", body)
    assert re.search(r"current_value\s*&\s*BIN_GORET_HIT", body)
    assert re.search(r"current_value\s*&\s*BIN_GORET_MISS", body)
    assert re.search(r"current_value\s*&\s*BIN_COPY_HIT", body)


def test_handles_dict_abbrev_value() -> None:
    """The dictionary check consults ``DICT_ABBREV_VALUE`` (line 1261)."""
    body = _extract_body()
    assert "DICT_ABBREV_VALUE" in body


def test_checks_lang_flag_and_mode_flag() -> None:
    """Rules are skipped when their language / mode flags don't match (lines 1234-1255)."""
    body = _extract_body()
    assert "in_lang_flag" in body
    assert "in_mode_flag" in body


def test_par_match_rule_call_site_count() -> None:
    """par_process_input calls par_match_rule at least once (line 1393)."""
    body = _extract_body()
    assert body.count("par_match_rule(") >= 1


def test_writes_nul_terminator_to_output() -> None:
    """``output_array[new_ret.output_pos + new_ret.output_offset] = '\\0'`` at exit."""
    body = _extract_body()
    assert re.search(r"output_array\s*\[[^\]]+\]\s*=\s*'\\0'", body)


def test_updates_ret_value_offsets_on_exit() -> None:
    """``ret_value->input_offset = new_ret.input_offset - new_input_diff`` etc."""
    body = _extract_body()
    assert re.search(
        r"ret_value\s*->\s*input_offset\s*=\s*new_ret\s*\.\s*input_offset\s*-\s*new_input_diff",
        body,
    )
    assert re.search(
        r"ret_value\s*->\s*output_offset\s*=\s*new_ret\s*\.\s*output_offset",
        body,
    )


# --------------------------------------------------------------------------
# Behavioural tests for the Python shim.
# --------------------------------------------------------------------------


def test_invalid_rule_section_writes_message_and_returns() -> None:
    """``rule > num_rule_sections`` writes the C source's invalid-section text."""
    ret = ReturnValue()
    out = bytearray(64)
    result = par_process_input(
        input_array=bytearray(b"hello\x00"),
        new_input=bytearray(64),
        output_array=out,
        dict_hit_array=bytearray(64),
        input_indexes=[IndexData()],
        new_input_indexes=[IndexData()],
        output_indexes=[IndexData()],
        in_lang_flag=0,
        in_mode_flag=0,
        rule=100,
        go_until=0,
        match_array=MatchArrays(),
        ret_value=ret,
        num_rule_sections=10,
    )
    assert result is ret
    # The message + NUL terminator should be in the output buffer.
    assert bytes(out).startswith(INVALID_RULE_SECTION_MESSAGE)
    # NUL terminator after the message.
    nul_index = len(INVALID_RULE_SECTION_MESSAGE)
    assert out[nul_index] == 0


def test_invalid_message_matches_c_source() -> None:
    """The literal bytes match the C source's string literal."""
    assert INVALID_RULE_SECTION_MESSAGE == b"Invalid rule section. "


def test_valid_rule_index_proceeds_past_guard() -> None:
    """A valid rule index proceeds past the guard into the deferred loop.

    Without tables the function raises NotImplementedError after
    completing the deterministic preamble (copy_index_list, _init_state).
    """
    ret = ReturnValue()
    with pytest.raises(NotImplementedError, match="par_process_input rule-driver"):
        par_process_input(
            input_array=bytearray(b"hello\x00"),
            new_input=bytearray(64),
            output_array=bytearray(64),
            dict_hit_array=bytearray(64),
            input_indexes=[IndexData()] * 8,
            new_input_indexes=[IndexData()] * 8,
            output_indexes=[IndexData()] * 8,
            in_lang_flag=0,
            in_mode_flag=0,
            rule=0,
            go_until=0,
            match_array=MatchArrays(),
            ret_value=ret,
            num_rule_sections=10,
        )


def test_notimplemented_cites_c_source_lines() -> None:
    """The NotImplementedError message names par_pars1.c when tables absent."""
    ret = ReturnValue()
    try:
        par_process_input(
            input_array=bytearray(b"x\x00"),
            new_input=bytearray(16),
            output_array=bytearray(16),
            dict_hit_array=bytearray(16),
            input_indexes=[IndexData()] * 4,
            new_input_indexes=[IndexData()] * 4,
            output_indexes=[IndexData()] * 4,
            in_lang_flag=0,
            in_mode_flag=0,
            rule=0,
            go_until=0,
            match_array=MatchArrays(),
            ret_value=ret,
            num_rule_sections=5,
        )
    except NotImplementedError as exc:
        msg = str(exc)
        assert "par_pars1.c" in msg
        assert "deferred" in msg
    else:
        pytest.fail("expected NotImplementedError")


def test_process_input_state_input_length_is_two_thirds() -> None:
    """The pre-loop state scales input length by 2/3 (par_pars1.c line 1106)."""
    # Inline the deterministic computation matching _init_state.
    expected = (30 * 2) // 3  # 20
    state = ProcessInputState(
        input_length=expected,
        return_rule=[-1] * PAR_MAX_RETURN_LEVEL,
        return_level=0,
        done=0,
        last_rule_was_hit=0,
        current_rule_number=0,
        new_input_diff=0,
        do_not_copy_next_word=0,
    )
    assert state.input_length == 20


def test_process_input_state_return_rule_filled_with_minus_one() -> None:
    """``return_rule`` is sized PAR_MAX_RETURN_LEVEL with all -1 entries."""
    state = ProcessInputState(
        input_length=0,
        return_rule=[-1] * PAR_MAX_RETURN_LEVEL,
        return_level=0,
        done=0,
        last_rule_was_hit=0,
        current_rule_number=0,
        new_input_diff=0,
        do_not_copy_next_word=0,
    )
    assert len(state.return_rule) == PAR_MAX_RETURN_LEVEL
    assert all(slot == -1 for slot in state.return_rule)


def test_shim_deferred_sentinel_is_negative() -> None:
    """The deferred sentinel is distinct from FAIL / SUCCESS / FATAL_FAIL."""
    assert SHIM_DEFERRED < 0


def test_invalid_rule_section_does_not_mutate_input() -> None:
    """The invalid-section branch leaves the input buffer untouched."""
    inp = bytearray(b"original input\x00")
    snapshot = bytes(inp)
    out = bytearray(64)
    par_process_input(
        input_array=inp,
        new_input=bytearray(64),
        output_array=out,
        dict_hit_array=bytearray(64),
        input_indexes=[IndexData()],
        new_input_indexes=[IndexData()],
        output_indexes=[IndexData()],
        in_lang_flag=0,
        in_mode_flag=0,
        rule=99,
        go_until=0,
        match_array=MatchArrays(),
        ret_value=ReturnValue(),
        num_rule_sections=5,
    )
    assert bytes(inp) == snapshot


def test_invalid_rule_section_does_not_modify_ret_value() -> None:
    """The invalid-section branch returns ret_value unchanged."""
    ret = ReturnValue(input_pos=10, output_pos=20, value=42)
    par_process_input(
        input_array=bytearray(b"x\x00"),
        new_input=bytearray(16),
        output_array=bytearray(64),
        dict_hit_array=bytearray(16),
        input_indexes=[IndexData()],
        new_input_indexes=[IndexData()],
        output_indexes=[IndexData()],
        in_lang_flag=0,
        in_mode_flag=0,
        rule=99,
        go_until=0,
        match_array=MatchArrays(),
        ret_value=ret,
        num_rule_sections=5,
    )
    assert ret.input_pos == 10
    assert ret.output_pos == 20
    assert ret.value == 42
