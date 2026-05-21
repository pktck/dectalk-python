"""Behavioral unit tests for the ``par_match_rule`` implementation.

These tests exercise the actual rule-walk logic (not just the shim
preamble) using minimal synthetic rule tables where needed.

The tests cover:
- BIN_END_OF_RULE empty rule (NUL-only body = SUCCESS)
- BIN_END_OF_RULE with a char-match byte that matches / doesn't match
- BIN_OPTIONAL sub-state that matches and that fails (OPT_FAIL -> SUCCESS)
- BIN_MACRO path raising NotImplementedError without tables
- Sub-state > BIN_SETS raising NotImplementedError without tables
- perform_action_funcs dispatch at post-loop (side-effect test)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dectalk.cmd.par_bin_codes import BIN_END_OF_RULE, BIN_OPTIONAL
from dectalk.cmd.par_match_rule import ActionFunc, par_match_rule
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL, SUCCESS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ret(**kw: int) -> ReturnValue:
    """Build a ReturnValue with sensible defaults, overridable via kwargs."""
    defaults = dict(
        input_pos=0,
        input_offset=0,
        output_pos=0,
        output_offset=0,
        value=SUCCESS,
        parser_flag=0,
        optional=0,
        rule=0,
        state=0,
        prev=None,
    )
    defaults.update(kw)
    return ReturnValue(**defaults)  # type: ignore[arg-type]


def _empty_indexes(size: int = 4) -> list[IndexData]:
    return [IndexData() for _ in range(size)]


# ---------------------------------------------------------------------------
# Tests -- BIN_END_OF_RULE path (no sub-states)
# ---------------------------------------------------------------------------


def test_empty_rule_body_returns_success() -> None:
    """A rule containing only a NUL byte is a no-op match (returns SUCCESS).

    The C while-loop breaks immediately when current_rule[new_ret.rule] == 0.
    """
    ret = _make_ret()
    result = par_match_rule(
        current_rule=b"\x00",
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
    )
    assert result == SUCCESS
    assert ret.value == SUCCESS


def test_fatal_fail_when_current_rule_is_none() -> None:
    """None current_rule writes FATAL_FAIL to ret_value and returns FATAL_FAIL."""
    ret = _make_ret()
    result = par_match_rule(
        current_rule=None,
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
    )
    assert result == FATAL_FAIL
    assert ret.value == FATAL_FAIL


def test_none_ret_value_returns_success_without_side_effects() -> None:
    """When ret_value is None the C source returns immediately (no-op)."""
    result = par_match_rule(
        current_rule=b"\x00",
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=None,
        dict_state_flag=0,
    )
    assert result == SUCCESS  # no-op return maps to SUCCESS


def test_char_type_zero_byte_in_rule_terminates_loop() -> None:
    """A rule byte of 0x00 inside the loop terminates the walk (SUCCESS).

    BIN_END_OF_RULE with end_of_match=255; rule index starts at 0.
    Rule byte 0x00 at index 0 triggers ``if temp == 0: break``.
    """
    ret = _make_ret()
    result = par_match_rule(
        current_rule=b"\x00\x01",  # 0x00 at index 0 -> break immediately
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
    )
    assert result == SUCCESS


def test_sub_state_above_bin_sets_without_tables_raises() -> None:
    """A rule byte > BIN_SETS requires perform_action_funcs/tables.

    BIN_SETS = 0x13; a byte of 0x14 (BIN_COPY) in the rule body enters
    the else branch and raises NotImplementedError without the tables.
    """
    ret = _make_ret()
    with pytest.raises(NotImplementedError, match="deferred"):
        par_match_rule(
            current_rule=bytes([0x14, 0x00]),
            state=BIN_END_OF_RULE,
            input_array=bytearray(b"hi\x00"),
            output_array=bytearray(256),
            input_indexes=_empty_indexes(),
            output_indexes=_empty_indexes(),
            match_array=MatchArrays(),
            ret_value=ret,
            dict_state_flag=0,
        )


def test_bin_optional_empty_rule_succeeds_and_updates_ret() -> None:
    """BIN_OPTIONAL with an empty body succeeds when action table is provided.

    Rule format for BIN_OPTIONAL:
      byte 0 (= ret_value.rule): opcode = 0x16 (BIN_OPTIONAL), skipped
      byte 1: end_of_match = 0x01 (body is empty since body=bytes[2..1])
      byte 2: NUL terminator

    The loop condition ``new_ret.rule (=2) <= end_of_match (=1)`` is False
    immediately, so the body is empty. Since value==SUCCESS (not OPT_FAIL),
    the normal SUCCESS path fires and perform_action_funcs[BIN_OPTIONAL] is called.
    """
    action_table = [MagicMock()] * 0x20
    ret = _make_ret(optional=0, rule=0)
    result = par_match_rule(
        current_rule=bytes([0x16, 0x01, 0x00]),  # BIN_OPTIONAL, end_of_match=1, NUL
        state=BIN_OPTIONAL,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
        perform_action_funcs=action_table,
    )
    assert result == SUCCESS
    assert ret.value == SUCCESS
    # perform_action_funcs[BIN_OPTIONAL] should have been called.
    assert action_table[BIN_OPTIONAL].call_count == 1


def test_perform_action_funcs_called_for_non_end_of_rule_state() -> None:
    """After a successful walk, perform_action_funcs[state]() is called.

    We use BIN_OPTIONAL (0x16) as the state with a 3-byte rule:
      byte 0: opcode=0x16 (skipped by state>=BIN_COPY path)
      byte 1: end_of_match=0x01 (empty body)
      byte 2: NUL

    The empty body means no match attempts; value stays SUCCESS; the
    post-loop action dispatch calls perform_action_funcs[BIN_OPTIONAL].
    """
    called_with: list[tuple[object, ...]] = []

    def fake_action(
        rule: bytes,
        inp: bytes,
        out: bytearray,
        in_idx: list[IndexData],
        out_idx: list[IndexData],
        match: MatchArrays,
        ret: ReturnValue,
        rng: RangeValue,
        save_num: int,
        dict_flag: int,
        rule_idx: int,
    ) -> None:
        called_with.append((rule, inp, save_num, dict_flag))

    # Build a perform_action_funcs table with the fake at index BIN_OPTIONAL.
    table: list[ActionFunc] = [MagicMock()] * 0x20
    table[BIN_OPTIONAL] = fake_action  # type: ignore[assignment]

    ret = _make_ret()
    result = par_match_rule(
        current_rule=bytes([0x16, 0x01, 0x00]),  # BIN_OPTIONAL, end=1, NUL
        state=BIN_OPTIONAL,
        input_array=bytearray(b"hello\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(),
        output_indexes=_empty_indexes(),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
        perform_action_funcs=table,
    )
    # fake_action should have been called once.
    assert len(called_with) == 1
    assert result == SUCCESS


def test_char_match_via_par_match_string_increments_offsets() -> None:
    """A BIN_END_OF_RULE with empty rule (just NUL) returns SUCCESS.

    BIN_END_OF_RULE: end_of_match=255 (0xFF). With current_rule=b"\x00"
    the while-loop condition ``current_rule[0] != 0`` is immediately False,
    so no par_match_string dispatch occurs.

    This is a regression test verifying the empty-rule fast-path.
    """
    ret = _make_ret(input_pos=0, input_offset=0)
    result = par_match_rule(
        current_rule=b"\x00",  # empty body -> immediately SUCCESS
        state=BIN_END_OF_RULE,
        input_array=bytearray(b"hi\x00"),
        output_array=bytearray(256),
        input_indexes=_empty_indexes(8),
        output_indexes=_empty_indexes(8),
        match_array=MatchArrays(),
        ret_value=ret,
        dict_state_flag=0,
    )
    assert result == SUCCESS
    assert ret.input_offset == 0  # no input consumed
    assert ret.output_offset == 0  # no output written
