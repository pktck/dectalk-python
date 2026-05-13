"""``par_process_input`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 1007-1730.

The top-level rule-tabling driver -- the outer loop of the LTS rule
engine. ``par_process_input`` walks the input string word by word,
skipping whitespace, picking up the rule-section's starting rule
number, and for each rule looks up the compiled bytes from
``rule_data_table`` (indexed via ``rule_index_table``) before
dispatching to :func:`par_match_rule`. After each match it
reconciles the new input / output windows, handles dictionary
hit / miss branches (``BIN_DICT_HIT`` / ``BIN_DICT_MISS``), follows
``NEXT_HIT`` / ``NEXT_MISS`` / ``GORET_HIT`` / ``GORET_MISS``
jumps, and emits the matched bytes to ``output_array``.

This module is a **structural placeholder**. The real Linux pipeline
short-circuits through :class:`dectalk._capi.CAPI`, which links the
shared ``libtts_us.so`` and produces byte-identical WAV output. The
Python rule engine that this function will eventually drive has not
been wired up yet, so the shim:

1. Captures the C signature (14 arguments) as a Python entry point
   with explicit dataclass types.
2. Validates the ``rule`` section index against
   ``num_rule_sections``, returning early with the C source's
   ``"Invalid rule section. "`` text written into ``output_array``
   when out of range (lines 1089-1096).
3. For the actual word-by-word driving loop, raises
   :class:`NotImplementedError` with a C-source-line citation so
   callers know this needs the engine wired.

The Linux ``_capi`` path provides the bit-identical output today;
this port is a structural placeholder for the eventual Python rule
engine. Tests for the underlying matcher families
(``par_match_string``, ``par_match_set``, ``par_match_digits``,
``par_match_standard``, ``par_look_ahead`` etc.) cover the leaf
behaviour, and ``tests/parity/`` checks end-to-end output against
the binary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.cmd.par_limits import PAR_MAX_RETURN_LEVEL
from dectalk.cmd.par_structs import IndexData, MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FAIL

SHIM_DEFERRED: Final[int] = -1
"""Status code returned by helpers when the rule-engine driver is
deferred. Callers that detect this value should treat it as
"engine not wired in" rather than as a real failure."""

INVALID_RULE_SECTION_MESSAGE: Final[bytes] = b"Invalid rule section. "
"""Bytes the C source writes into ``output_array`` when the requested
rule section is out of range -- see par_pars1.c line 1094."""


@dataclass(slots=True)
class ProcessInputState:
    r"""Captured deterministic state for one ``par_process_input`` call.

    Mirrors the locals the C function initialises before the
    ``while (new_input[...]!='\0')`` loop at par_pars1.c line 1109.
    Useful for tests that want to inspect the pre-loop snapshot
    without driving the rule walk.

    Attributes:
        input_length: ``(strlen(input_array) * 2) / 3`` -- see line 1106.
        return_rule: ``PAR_MAX_RETURN_LEVEL`` slots, memset to ``-1``.
            Used as the GORET return-stack (lines 1097 / 1055).
        return_level: Current depth into ``return_rule`` (line 1056).
        done: Outer-loop termination flag (line 1049).
        last_rule_was_hit: Tracks whether the previous rule hit, for
            chained next-hit logic (line 1053).
        current_rule_number: Index into ``rule_index_table`` for the
            rule about to be processed (line 1054).
        new_input_diff: Cumulative diff between ``new_input`` and
            ``input_array`` sizes (line 1058). Used to convert the
            new-input cursor back to the caller's frame at exit.
        do_not_copy_next_word: Set to ``1`` when an action wrote
            whitespace into the output so the next word should be
            kept (line 1061).
    """

    input_length: int
    return_rule: list[int]
    return_level: int
    done: int
    last_rule_was_hit: int
    current_rule_number: int
    new_input_diff: int
    do_not_copy_next_word: int


def _init_state(input_length: int) -> ProcessInputState:
    """Build the deterministic pre-loop state.

    Faithful translation of par_pars1.c lines 1031-1106:

    * ``return_rule`` is memset to ``-1`` (line 1097).
    * ``input_length = (strlen(input_array) * 2) / 3`` (line 1106).
    * All other ints start at the defaults shown in the dataclass.
    """
    return ProcessInputState(
        input_length=(input_length * 2) // 3,
        return_rule=[-1] * PAR_MAX_RETURN_LEVEL,
        return_level=0,
        done=0,
        last_rule_was_hit=0,
        current_rule_number=0,
        new_input_diff=0,
        do_not_copy_next_word=0,
    )


def par_process_input(
    input_array: bytearray | None,
    new_input: bytearray | None,
    output_array: bytearray | None,
    dict_hit_array: bytearray | None,
    input_indexes: IndexData,
    new_input_indexes: IndexData,
    output_indexes: IndexData,
    in_lang_flag: int,
    in_mode_flag: int,
    rule: int,
    go_until: int,
    match_array: MatchArrays | None,
    ret_value: ReturnValue,
    *,
    num_rule_sections: int = 0,
) -> ReturnValue:
    r"""Drive the rule-table parser over ``input_array`` (shim).

    Faithful translation of the C function preamble at par_pars1.c
    lines 1007-1106:

    .. code-block:: c

        preturn_value_t par_process_input(LPTTS_HANDLE_T phTTS,
                                          unsigned char *input_array,
                                          unsigned char *new_input,
                                          unsigned char *output_array,
                                          unsigned char *dict_hit_array,
                                          pindex_data_t input_indexes,
                                          pindex_data_t new_input_indexes,
                                          pindex_data_t output_indexes,
                                          U32 in_lang_flag,
                                          U32 in_mode_flag,
                                          int rule,
                                          int go_until,
                                          pmatch_arrays_t match_array,
                                          preturn_value_t ret_value)
        {
            return_value_t new_ret = {0,0,0,0,0,0,0,0};
            ...
            if (rule > num_rule_sections) {
                printf("par_process_input; no such rule section %d\n", rule);
                strcpy(output_array, "Invalid rule section. ");
                return ret_value;
            }
            memset(return_rule, -1, sizeof(return_rule));
            input_length = strlen(input_array);
            strcpy(new_input, input_array);
            memcpy(new_input_indexes, input_indexes,
                   input_length * sizeof(index_data_t));
            input_length = (input_length * 2) / 3;
            while (((new_input[new_ret.input_pos + new_ret.input_offset] != '\0')
                    && (go_until == 0)) ||
                   (((new_ret.input_pos + new_ret.input_offset - new_input_diff)
                     < input_length) && (go_until == 1))) {
                ...
            }
            output_array[new_ret.output_pos + new_ret.output_offset] = '\0';
            ret_value->input_offset = new_ret.input_offset - new_input_diff;
            ret_value->output_offset = new_ret.output_offset;
            return ret_value;
        }

    The ``rule > num_rule_sections`` guard (lines 1089-1096) is
    implemented here -- it writes ``"Invalid rule section. "`` into
    ``output_array`` and returns ``ret_value`` unchanged. The
    ``return_rule`` memset and the ``input_length`` /
    ``new_input`` copying preamble are also reproduced so callers
    can observe the same pre-loop state shape.

    The deferred portion is the giant ``while`` loop at lines
    1109-1721 that calls :func:`par_match_rule`, handles
    dictionary-hit branches, and stitches the matched output back
    into ``new_input`` for chained rules.

    Args:
        input_array: Original input bytes. ``None`` passes through.
        new_input: Scratch input buffer (rules write back here on
            chained hits). The C source ``strcpy``s ``input_array``
            into this on entry.
        output_array: Output buffer to write into.
        dict_hit_array: Per-position dictionary-hit flags
            (``DICT_HIT_VALUE`` / ``DICT_MISS_VALUE`` /
            ``DICT_ABBREV_VALUE``) -- consulted by rules tagged with
            ``BIN_DICT_HIT`` / ``BIN_DICT_MISS``.
        input_indexes: Per-byte pipeline-index data for ``input_array``.
        new_input_indexes: Per-byte pipeline-index data for ``new_input``.
        output_indexes: Per-byte pipeline-index data for ``output_array``.
        in_lang_flag: 32-bit language flag (checked against each
            rule's first 32-bit mode word).
        in_mode_flag: 32-bit mode flag (checked against each rule's
            second 32-bit mode word).
        rule: Rule-section index. Out-of-range values trigger the
            "Invalid rule section. " early return.
        go_until: ``0`` -> drive until NUL terminator; ``1`` -> drive
            until ``new_ret.input_pos + input_offset -
            new_input_diff >= input_length``.
        match_array: Saved-string buffers (:class:`MatchArrays`).
        ret_value: Caller's :class:`ReturnValue`. The shim updates
            its ``input_offset`` / ``output_offset`` on exit, like
            the C source does at lines 1724-1725.
        num_rule_sections: Number of rule sections available. The C
            source pulls this from a global; we accept it as a
            keyword arg so tests can drive the out-of-range guard.

    Returns:
        ``ret_value``. When the rule index is out of range, the
        function writes ``b"Invalid rule section. "`` into
        ``output_array[0:]`` (matching the C source's
        ``strcpy(output_array, "Invalid rule section. ")``) and
        returns immediately.

    Raises:
        NotImplementedError: When inputs validate and the actual
            rule-walking loop (par_pars1.c lines 1109-1721) would
            need to fire. Callers that need rule-engine output
            must route through :class:`dectalk._capi.CAPI`; this
            shim is structural only.
    """
    # Suppress "unused" warnings for the index / language / mode
    # arguments that the deferred engine consumes.
    del input_indexes, new_input_indexes, output_indexes
    del in_lang_flag, in_mode_flag, go_until
    del dict_hit_array, match_array

    # Out-of-range rule index, par_pars1.c lines 1089-1096.
    # ``strcpy(output_array, "Invalid rule section. ")`` writes the
    # message plus a NUL terminator. We mirror that exactly so
    # callers see the byte-for-byte string the C source emits.
    if rule > num_rule_sections:
        if output_array is not None:
            payload = INVALID_RULE_SECTION_MESSAGE + b"\x00"
            length = min(len(payload), len(output_array))
            output_array[:length] = payload[:length]
        return ret_value

    # ``input_array`` is dereferenced unconditionally by the C
    # source (strlen). Replicate the implicit "we need an input" by
    # short-circuiting with FAIL when the buffer is absent -- the C
    # source would crash here, but Python should fail cleanly.
    if input_array is None or new_input is None or output_array is None:
        ret_value.value = FAIL
        return ret_value

    # par_pars1.c line 1099: input_length = strlen(input_array).
    # Python: search for the first NUL or use the whole buffer.
    nul_pos = input_array.find(0)
    input_length = nul_pos if nul_pos >= 0 else len(input_array)

    # par_pars1.c line 1101: strcpy(new_input, input_array). Copy
    # input_array's bytes (through the NUL) into new_input so the
    # pre-loop state matches what the engine would observe.
    copy_len = min(input_length + 1, len(new_input))
    new_input[:copy_len] = input_array[:copy_len]
    # Pad NUL terminator if there's room.
    if copy_len < len(new_input):
        new_input[copy_len] = 0

    # Build the deterministic pre-loop state. ``return_rule`` is
    # memset to -1 (line 1097); ``input_length`` is scaled by 2/3
    # (line 1106).
    state = _init_state(input_length)

    # The rule-tabling loop body (par_pars1.c lines 1109-1721)
    # depends on rule_data_table / rule_index_table and on
    # par_match_rule's full implementation -- both deferred.
    raise NotImplementedError(
        "par_process_input rule-driver loop (par_pars1.c lines 1109-1721) is "
        "deferred -- the Linux dectalk._capi.CAPI path provides bit-identical "
        "output today; wiring up the Python rule engine requires the "
        "rule_data_table / rule_index_table and par_match_rule's full "
        f"implementation. Got rule={rule} go_until=deferred "
        f"input_length={input_length} state.input_length={state.input_length}."
    )


__all__ = [
    "INVALID_RULE_SECTION_MESSAGE",
    "SHIM_DEFERRED",
    "ProcessInputState",
    "par_process_input",
]
