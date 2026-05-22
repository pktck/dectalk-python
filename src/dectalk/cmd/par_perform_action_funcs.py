"""``perform_action_funcs`` dispatch table for the cmd-stage rule engine.

Mirrors the C source's static 0x20-entry function-pointer table in
``src/dapi/src/cmd/par_pars1.c`` lines 651-704. Each slot is the
function called by ``par_match_rule`` when it encounters the
corresponding rule-action opcode.

The table is built around the existing Python action ports under
``dectalk.cmd.par_*``. Three actions in C take a *long* uniform
signature (``current_rule, input_array, output_array,
input_indexes, output_indexes, match_array, ret_value, range_value,
save_num, dict_state_flag, in_rule_index[, insert_operation_flags]``)
while their Python ports use the shorter signature appropriate to
each action's actual needs. The adapter wrappers below absorb the
extra arguments so callers can dispatch uniformly.

ERROR_func1 / ERROR_func2 are diagnostic stubs in C (one writes a
mocking string, the other is a no-op). We surface them as Python
no-ops (no-op suffices for parity since the real engine should
never invoke them on valid rules).
"""

from __future__ import annotations

from typing import Final

from dectalk.cmd.par_check_word_string import par_check_word_string as _par_check_word_string
from dectalk.cmd.par_compound_break import par_compound_break as _par_compound_break
from dectalk.cmd.par_delete_string import par_delete_string as _par_delete_string
from dectalk.cmd.par_dom_dict_search import par_dom_dict_search as _par_dom_dict_search
from dectalk.cmd.par_insert_string import par_insert_string as _par_insert_string
from dectalk.cmd.par_insert_string_after import par_insert_string_after as _par_insert_string_after
from dectalk.cmd.par_insert_string_before import (
    par_insert_string_before as _par_insert_string_before,
)
from dectalk.cmd.par_match_rule import ActionFunc
from dectalk.cmd.par_replace_string import par_replace_string as _par_replace_string
from dectalk.cmd.par_save_string import par_save_string as _par_save_string
from dectalk.cmd.par_status_string import par_status_string as _par_status_string
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

# ---------------------------------------------------------------------------
# ERROR stub adapters (par_pars1.c lines 609-650).
# ---------------------------------------------------------------------------


def _ERROR_func1(  # noqa: N802 - mirrors C name
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """``ERROR_func1`` from par_pars1.c lines 609-630.

    The C source writes a literal pud-fart string into the output for
    debugging when an undefined action opcode is dispatched. We don't
    bother emulating that exactly — well-formed rules never trigger
    these slots, and we'd rather raise loud than write garbage. But
    for compatibility with the dispatch table layout, accept the full
    11-argument signature.
    """
    # Touch ret_value so it's not unused, mirroring C behaviour shape.
    del ret_value, output_array


def _ERROR_func2(  # noqa: N802 - mirrors C name
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """``ERROR_func2`` from par_pars1.c lines 631-650.

    Pure no-op in the C source.
    """
    return


# ---------------------------------------------------------------------------
# Short-signature adapters
# ---------------------------------------------------------------------------


def _adapt_delete_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapt the dispatch signature down to ``par_delete_string``.

    The Python port uses the shorter ``(output_array, output_indexes,
    ret_value)`` signature; this adapter absorbs the unused extras.
    """
    _par_delete_string(output_array, output_indexes, ret_value)


def _adapt_save_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapt the dispatch signature down to ``par_save_string``.

    The Python port uses the shorter ``(output_array, num, match_array,
    ret_value)`` signature; this adapter absorbs the unused extras.
    """
    _par_save_string(bytes(output_array), save_num, match_array, ret_value)


def _adapt_check_word_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapt the dispatch signature down to ``par_check_word_string``.

    The Python port uses the shorter ``(output_array, ret_value)``
    signature; this adapter absorbs the unused extras.
    """
    _par_check_word_string(bytes(output_array), ret_value)


# ---------------------------------------------------------------------------
# 12-arg -> 11-arg adapters for the GERMAN_COMPOUND_NOUNS-style ports
# ---------------------------------------------------------------------------


def _adapt_replace_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0).

    The Python port of ``par_replace_string`` keeps the 12-arg shape from
    the GERMAN_COMPOUND_NOUNS build. The dispatch table we expose is
    the 11-arg form (in line with the non-GCN ``ActionFunc`` type
    alias) — we forward to the longer Python signature with
    ``insert_operation_flags=0``.
    """
    _par_replace_string(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_insert_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_insert_string(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_insert_string_after(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_insert_string_after(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_insert_string_before(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_insert_string_before(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_compound_break(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_compound_break(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_dom_dict_search(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_dom_dict_search(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


def _adapt_status_string(
    current_rule: bytes,
    input_array: bytes,
    output_array: bytearray,
    input_indexes: list[IndexData],
    output_indexes: list[IndexData],
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    save_num: int,
    dict_state_flag: int,
    in_rule_index: int,
) -> None:
    """Adapter that drops ``insert_operation_flags`` (default 0)."""
    _par_status_string(
        current_rule,
        bytearray(input_array),
        output_array,
        input_indexes,
        output_indexes,
        match_array,
        ret_value,
        range_value,
        save_num,
        dict_state_flag,
        in_rule_index,
        0,
    )


# ---------------------------------------------------------------------------
# The 0x20-entry dispatch table (non-GERMAN_COMPOUND_NOUNS build layout).
# Mirrors par_pars1.c lines 666-703.
# ---------------------------------------------------------------------------

PERFORM_ACTION_FUNCS: Final[tuple[ActionFunc, ...]] = (
    # 0x00..0x13: error slots (no valid rule action lives below 0x14).
    _ERROR_func2,  # 0x00
    _ERROR_func1,  # 0x01
    _ERROR_func1,  # 0x02
    _ERROR_func1,  # 0x03
    _ERROR_func1,  # 0x04
    _ERROR_func1,  # 0x05
    _ERROR_func1,  # 0x06
    _ERROR_func1,  # 0x07
    _ERROR_func1,  # 0x08
    _ERROR_func1,  # 0x09
    _ERROR_func1,  # 0x0A
    _ERROR_func1,  # 0x0B
    _ERROR_func1,  # 0x0C
    _ERROR_func1,  # 0x0D
    _ERROR_func1,  # 0x0E
    _ERROR_func1,  # 0x0F
    _ERROR_func1,  # 0x10
    _ERROR_func1,  # 0x11
    _ERROR_func1,  # 0x12
    _ERROR_func1,  # 0x13
    _ERROR_func2,  # 0x14 BIN_COPY -- shouldn't be dispatched here
    _adapt_delete_string,  # 0x15 BIN_DELETE
    _ERROR_func2,  # 0x16
    _adapt_save_string,  # 0x17 BIN_SAVE
    _ERROR_func2,  # 0x18
    _adapt_replace_string,  # 0x19 BIN_REPLACE
    _adapt_insert_string,  # 0x1A BIN_INSERT
    # 0x1B / 0x1C: non-GERMAN_COMPOUND_NOUNS build layout.
    _adapt_insert_string_after,  # 0x1B
    _adapt_insert_string_before,  # 0x1C
    _adapt_dom_dict_search,  # 0x1D BIN_DICTIONARY (dom dict)
    _adapt_status_string,  # 0x1E BIN_STATUS
    _adapt_check_word_string,  # 0x1F BIN_CHECK_WORD
)
"""Dispatch table for cmd-stage rule actions, indexed by 5-bit opcode.

Mirrors the static ``perform_action_funcs`` table at par_pars1.c
lines 651-704. The non-GERMAN_COMPOUND_NOUNS slots (0x1B
``par_insert_string_after`` / 0x1C ``par_insert_string_before``)
are surfaced here so the Python rule engine can drive both
build variants from the same table — the GCN entries
(``par_compound_break``, ``ERROR_func2``) are available via
:data:`PERFORM_ACTION_FUNCS_GCN`.
"""


PERFORM_ACTION_FUNCS_GCN: Final[tuple[ActionFunc, ...]] = (
    *PERFORM_ACTION_FUNCS[:0x1B],
    _adapt_compound_break,
    _ERROR_func2,
    *PERFORM_ACTION_FUNCS[0x1D:],
)
"""Dispatch table variant for the GERMAN_COMPOUND_NOUNS build.

The only difference vs :data:`PERFORM_ACTION_FUNCS` is that opcode
0x1B routes to :func:`par_compound_break` instead of
:func:`par_insert_string_after`, and 0x1C is a no-op error slot
instead of :func:`par_insert_string_before`. See par_pars1.c lines
695-700 for the C ``#ifdef GERMAN_COMPOUND_NOUNS`` branch.
"""


__all__ = [
    "PERFORM_ACTION_FUNCS",
    "PERFORM_ACTION_FUNCS_GCN",
]
