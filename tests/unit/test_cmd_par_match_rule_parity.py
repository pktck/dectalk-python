"""C-source parity test for ``par_match_rule`` against par_pars1.c.

Re-parses the C function body (lines 2016-2430) via brace-depth
tracking. The signature spans an ``#ifdef PARSER_STANDALONE_DEBUG``
block so we anchor on the ``void par_match_rule(`` definition that
the Linux build actually compiles and then walk the brace pair.

Behavioural tests cover the Python shim's deterministic pieces
(NULL-pointer ``FATAL_FAIL`` short-circuit, ``ret_value == NULL``
no-op early return, post-validation ``NotImplementedError`` for the
deferred rule walk).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_DICTIONARY,
    BIN_END_OF_RULE,
    BIN_MACRO,
    BIN_OPTIONAL,
    BIN_SAVE,
)
from dectalk.cmd.par_match_rule import (
    SHIM_DEFERRED,
    MatchRuleInputs,
    par_match_rule,
    par_match_rule_validate,
)
from dectalk.cmd.par_structs import IndexData, MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL, SUCCESS

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``par_match_rule`` definition body via brace depth."""
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"void\s+par_match_rule\s*\(\s*unsigned\s+char\s*\*\s*current_rule"
            r"[^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_match_rule definition not found"
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
    return text[start:i]


# --------------------------------------------------------------------------
# C-source structural tests (~10 key patterns).
# --------------------------------------------------------------------------


def test_signature_takes_nine_parameters() -> None:
    """par_match_rule has nine positional parameters in the Linux build."""
    text = _read_par_pars1_c()
    assert re.search(
        r"void\s+par_match_rule\s*\(\s*"
        r"unsigned\s+char\s*\*\s*current_rule\s*,\s*"
        r"int\s+state\s*,",
        text,
    )
    assert re.search(r"unsigned\s+char\s*\*\s*input_array", text)
    assert re.search(r"unsigned\s+char\s*\*\s*output_array", text)
    assert re.search(r"pindex_data_t\s+input_indexes", text)
    assert re.search(r"pindex_data_t\s+output_indexes", text)
    assert re.search(r"pmatch_arrays_t\s+match_array", text)
    assert re.search(r"preturn_value_t\s+ret_value", text)
    assert re.search(r"int\s+dict_state_flag", text)


def test_sanity_checking_short_circuits_on_null_ret_value() -> None:
    """``if (ret_value == NULL) return;`` lives inside the SANITY_CHECKING block."""
    body = _extract_body()
    assert "SANITY_CHECKING" in body
    assert re.search(r"ret_value\s*==\s*NULL", body)


def test_null_pointer_check_writes_fatal_fail() -> None:
    """When other pointers are NULL the value is set to FATAL_FAIL."""
    body = _extract_body()
    # Match either order of the NULL check
    assert re.search(r"current_rule\s*==\s*NULL", body)
    assert re.search(r"ret_value\s*->\s*value\s*=\s*FATAL_FAIL", body)


def test_initialises_new_ret_from_caller() -> None:
    """``new_ret.input_pos = ret_value->input_pos + ret_value->input_offset`` etc."""
    body = _extract_body()
    assert re.search(
        r"new_ret\s*\.\s*input_pos\s*=\s*ret_value\s*->\s*input_pos\s*\+\s*ret_value\s*->\s*input_offset",
        body,
    )
    assert re.search(
        r"new_ret\s*\.\s*output_pos\s*=\s*ret_value\s*->\s*output_pos\s*\+\s*ret_value\s*->\s*output_offset",
        body,
    )


def test_handles_bin_end_of_rule_state() -> None:
    """``state == BIN_END_OF_RULE`` sets end_of_match to 255 (line 2089)."""
    body = _extract_body()
    assert re.search(r"state\s*==\s*BIN_END_OF_RULE", body)
    assert re.search(r"end_of_match\s*=\s*255", body)


def test_handles_bin_optional_state() -> None:
    """``state == BIN_OPTIONAL`` sets ``new_ret.optional = 1`` (line 2098)."""
    body = _extract_body()
    assert re.search(r"state\s*==\s*BIN_OPTIONAL", body)
    assert re.search(r"new_ret\s*\.\s*optional\s*=\s*1", body)


def test_handles_bin_save_and_bin_dictionary_states() -> None:
    """BIN_SAVE / BIN_DICTIONARY pull save_state_num from the rule body."""
    body = _extract_body()
    assert re.search(r"state\s*==\s*BIN_SAVE", body)
    assert re.search(r"state\s*==\s*BIN_DICTIONARY", body)
    assert "save_state_num" in body


def test_handles_bin_macro_state() -> None:
    """BIN_MACRO recurses into the named rule (line 2129)."""
    body = _extract_body()
    assert re.search(r"state\s*==\s*BIN_MACRO", body)
    # The macro state recursively calls par_match_rule with BIN_END_OF_RULE.
    assert re.search(r"par_match_rule\s*\([^)]*BIN_END_OF_RULE", body)


def test_dispatches_to_par_match_string_for_small_opcodes() -> None:
    """Operations <= BIN_SETS dispatch to par_match_string (line 2227)."""
    body = _extract_body()
    assert re.search(r"new_operation\s*<=\s*BIN_SETS", body)
    assert "par_match_string(" in body


def test_recurses_for_higher_opcodes() -> None:
    """For larger opcodes the body recurses into par_match_rule (line 2262)."""
    body = _extract_body()
    # Match the recursive self-call inside the dispatch.
    assert body.count("par_match_rule(") >= 2


def test_returns_fatal_fail_on_end_of_state_mismatch() -> None:
    """``if (new_ret.rule != (end_of_match+1))`` -> FATAL_FAIL (line 2341-2346)."""
    body = _extract_body()
    assert re.search(r"end_of_match\s*\+\s*1", body)
    # FATAL_FAIL is set on the end-of-state mismatch.
    assert body.count("FATAL_FAIL") >= 2


def test_calls_perform_action_funcs_jump_table() -> None:
    """The post-loop action call uses ``perform_action_funcs[state]`` (line 2356)."""
    body = _extract_body()
    assert "perform_action_funcs" in body


def test_handles_optional_sub_match_via_opt_fail() -> None:
    """OPT_FAIL is returned for failed optional sub-matches (line 2237 / 2274)."""
    body = _extract_body()
    assert "OPT_FAIL" in body


def test_handles_end_of_string_propagation() -> None:
    """END_OF_STRING is propagated up from a sub-match (line 2243 / 2279)."""
    body = _extract_body()
    assert body.count("END_OF_STRING") >= 3


# --------------------------------------------------------------------------
# Behavioural tests for the Python shim.
# --------------------------------------------------------------------------


def test_validate_returns_success_when_all_pointers_valid() -> None:
    """Validation passes when all four required pointers are non-None."""
    ret = ReturnValue()
    result = par_match_rule_validate(
        current_rule=b"\x00",
        input_array=bytearray(b"abc"),
        output_array=bytearray(b""),
        match_array=MatchArrays(),
        ret_value=ret,
    )
    assert result == SUCCESS


def test_validate_returns_fatal_fail_on_null_current_rule() -> None:
    """A NULL current_rule triggers FATAL_FAIL (par_pars1.c line 2060)."""
    ret = ReturnValue()
    result = par_match_rule_validate(
        current_rule=None,
        input_array=bytearray(b""),
        output_array=bytearray(b""),
        match_array=MatchArrays(),
        ret_value=ret,
    )
    assert result == FATAL_FAIL
    assert ret.value == FATAL_FAIL


def test_validate_returns_fatal_fail_on_null_input() -> None:
    """A NULL input_array triggers FATAL_FAIL too."""
    ret = ReturnValue()
    result = par_match_rule_validate(
        current_rule=b"",
        input_array=None,
        output_array=bytearray(b""),
        match_array=MatchArrays(),
        ret_value=ret,
    )
    assert result == FATAL_FAIL
    assert ret.value == FATAL_FAIL


def test_validate_no_op_on_null_ret_value() -> None:
    """When ret_value is NULL the C source returns without action."""
    result = par_match_rule_validate(
        current_rule=b"",
        input_array=bytearray(b""),
        output_array=bytearray(b""),
        match_array=MatchArrays(),
        ret_value=None,
    )
    assert result == SUCCESS


def test_par_match_rule_short_circuits_when_ret_value_is_none() -> None:
    """``par_match_rule`` returns immediately when ret_value is None."""
    result = par_match_rule(
        current_rule=None,
        state=BIN_END_OF_RULE,
        input_array=None,
        output_array=None,
        input_indexes=IndexData(),
        output_indexes=IndexData(),
        match_array=None,
        ret_value=None,
        dict_state_flag=0,
    )
    assert result == SUCCESS


def test_par_match_rule_marks_fatal_fail_for_null_pointer() -> None:
    """A non-None ret_value with a NULL current_rule gets FATAL_FAIL."""
    ret = ReturnValue()
    result = par_match_rule(
        current_rule=None,
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hello"),
        output_array=bytearray(b""),
        input_indexes=IndexData(),
        output_indexes=IndexData(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
    )
    assert result == FATAL_FAIL
    assert ret.value == FATAL_FAIL


def test_par_match_rule_raises_not_implemented_for_deferred_walk() -> None:
    """With valid inputs the shim defers the actual rule walk."""
    ret = ReturnValue()
    with pytest.raises(NotImplementedError, match="par_match_rule rule-walk"):
        par_match_rule(
            current_rule=b"\x00",
            state=BIN_END_OF_RULE,
            input_array=bytearray(b"hi"),
            output_array=bytearray(b""),
            input_indexes=IndexData(),
            output_indexes=IndexData(),
            match_array=MatchArrays(),
            ret_value=ret,
            dict_state_flag=0,
        )


def test_par_match_rule_notimplemented_cites_c_source() -> None:
    """The NotImplementedError mentions par_pars1.c so callers know where to look."""
    ret = ReturnValue()
    try:
        par_match_rule(
            current_rule=b"\x00",
            state=BIN_END_OF_RULE,
            input_array=bytearray(b""),
            output_array=bytearray(b""),
            input_indexes=IndexData(),
            output_indexes=IndexData(),
            match_array=MatchArrays(),
            ret_value=ret,
            dict_state_flag=0,
        )
    except NotImplementedError as exc:
        msg = str(exc)
        assert "par_pars1.c" in msg
        assert "deferred" in msg
    else:
        pytest.fail("expected NotImplementedError")


def test_match_rule_inputs_dataclass_carries_signature() -> None:
    """:class:`MatchRuleInputs` mirrors the nine-argument C signature."""
    inputs = MatchRuleInputs(
        current_rule=b"\x00",
        state=BIN_DICTIONARY,
        input_array=bytearray(b""),
        output_array=bytearray(b""),
        input_indexes=IndexData(),
        output_indexes=IndexData(),
        match_array=MatchArrays(),
        ret_value=ReturnValue(),
        dict_state_flag=1,
    )
    assert inputs.state == BIN_DICTIONARY
    assert inputs.dict_state_flag == 1


def test_shim_deferred_sentinel_is_negative() -> None:
    """The deferred sentinel is distinguishable from real status codes."""
    # SUCCESS / FAIL / FATAL_FAIL are all non-negative -- the
    # shim sentinel must not collide with them.
    assert SHIM_DEFERRED < 0


def test_bin_state_opcodes_distinct() -> None:
    """The state opcodes the shim mentions are unique constants."""
    opcodes = {BIN_END_OF_RULE, BIN_OPTIONAL, BIN_SAVE, BIN_MACRO, BIN_DICTIONARY}
    assert len(opcodes) == 5
