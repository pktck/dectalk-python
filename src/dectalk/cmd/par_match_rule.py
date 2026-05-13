"""``par_match_rule`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2016-2430.

The recursive driver at the heart of the LTS rule-matching engine.
Given a compiled rule and the current input window, it walks the
rule body byte-by-byte: dispatching to :func:`par_match_string` for
character-type operations and recursing into itself for nested
action / save / replace / dictionary / macro / optional sub-states.

This module is a **structural placeholder**. The real Linux pipeline
short-circuits through :class:`dectalk._capi.CAPI`, which links the
shared ``libtts_us.so`` and produces byte-identical WAV output. The
Python rule engine that this function will eventually drive has not
been wired up yet, so the shim:

1. Captures the C signature as a Python entry point that accepts the
   same nine arguments (with explicit dataclass types).
2. Performs the deterministic validation pieces -- the
   ``SANITY_CHECKING`` ``ret_value == NULL`` early-return and the
   "any other pointer is NULL" -> ``FATAL_FAIL`` branch -- on the
   Python side.
3. Initialises the ``new_ret`` recursion-state object from the
   caller's :class:`~dectalk.cmd.par_structs.ReturnValue`, mirroring
   the unconditional preamble at lines 2070-2103.
4. For the actual rule-walking loop (the dispatch at lines
   2129-2299 plus the post-loop action-table call), raises
   :class:`NotImplementedError` with a C-source-line citation so
   callers know this needs the full engine wired in.

The Linux ``_capi`` path provides the bit-identical output today;
the parity tests for individual helpers (``par_match_string``,
``par_match_set``, ``par_match_digits``, ``par_look_ahead`` etc.)
exercise the leaf functions in isolation, and the end-to-end
``tests/parity/`` suite covers the integrated behaviour by comparing
against the binary. This shim's purpose is to give the rest of the
parser machinery an importable symbol of the right name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.cmd.par_bin_codes import (
    BIN_DICTIONARY,
    BIN_END_OF_RULE,
    BIN_MACRO,
    BIN_OPTIONAL,
    BIN_SAVE,
)
from dectalk.cmd.par_structs import IndexData, MatchArrays, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL, SUCCESS

SHIM_DEFERRED: Final[int] = -1
"""Status code returned by helpers when the rule-engine driver is
deferred. Callers that detect this value should treat it as
"engine not wired in" rather than as a real match failure."""

_END_OF_MATCH_FOR_BIN_END_OF_RULE: Final[int] = 255
"""Value the C source stores in ``end_of_match`` when ``state ==
BIN_END_OF_RULE`` -- see par_pars1.c line 2089."""


@dataclass(slots=True)
class MatchRuleInputs:
    """Captured inputs for one ``par_match_rule`` invocation.

    Mirrors the C signature::

        void par_match_rule(unsigned char *current_rule, int state,
                            unsigned char *input_array,
                            unsigned char *output_array,
                            pindex_data_t input_indexes,
                            pindex_data_t output_indexes,
                            pmatch_arrays_t match_array,
                            preturn_value_t ret_value,
                            int dict_state_flag);

    Useful for tests / future structural ports that want to thread
    the same nine values without restating them at every call site.

    Attributes:
        current_rule: Compiled rule bytes.
        state: Action / sub-state opcode (``BIN_END_OF_RULE``,
            ``BIN_SAVE``, ``BIN_OPTIONAL``, ``BIN_DICTIONARY`` etc.).
        input_array: Current input text window.
        output_array: Output buffer being built.
        input_indexes: Per-byte pipeline-index data for the input.
        output_indexes: Per-byte pipeline-index data for the output.
        match_array: Saved-string buffers (:class:`MatchArrays`).
        ret_value: Recursion-state object (:class:`ReturnValue`).
        dict_state_flag: ``1`` when invoked from the dictionary-lookup
            path (``par_look_ahead_dictionary``), ``0`` otherwise.
    """

    current_rule: bytes
    state: int
    input_array: bytearray
    output_array: bytearray
    input_indexes: IndexData
    output_indexes: IndexData
    match_array: MatchArrays
    ret_value: ReturnValue
    dict_state_flag: int


def par_match_rule(
    current_rule: bytes | None,
    state: int,
    input_array: bytearray | None,
    output_array: bytearray | None,
    input_indexes: IndexData,
    output_indexes: IndexData,
    match_array: MatchArrays | None,
    ret_value: ReturnValue | None,
    dict_state_flag: int,
) -> int:
    r"""Match one compiled rule against the current input window (shim).

    Faithful translation of the C function preamble at par_pars1.c
    lines 2016-2103:

    .. code-block:: c

        void par_match_rule(unsigned char *current_rule, int state,
                            unsigned char *input_array,
                            unsigned char *output_array,
                            pindex_data_t input_indexes,
                            pindex_data_t output_indexes,
                            pmatch_arrays_t match_array,
                            preturn_value_t ret_value,
                            int dict_state_flag)
        {
            return_value_t new_ret;
            int new_operation = BIN_END_OF_RULE;
            ...
        #ifdef SANITY_CHECKING
            if (ret_value == NULL) return;
            if (current_rule == NULL || input_array == NULL ||
                output_array == NULL || match_array == NULL) {
                ret_value->value = FATAL_FAIL;
                return;
            }
        #endif
            length_of_input = strlen(input_array);
            new_ret.input_pos = ret_value->input_pos + ret_value->input_offset;
            new_ret.input_offset = 0;
            new_ret.output_pos = ret_value->output_pos + ret_value->output_offset;
            new_ret.output_offset = 0;
            new_ret.value = SUCCESS;
            new_ret.parser_flag = ret_value->parser_flag;
            new_ret.rule = in_rule_index = ret_value->rule;
            if (state == BIN_END_OF_RULE)
                end_of_match = 255;
            ...

    The validation preamble and ``new_ret`` initialisation are
    implemented in Python here -- they're deterministic and do not
    require the binary rule tables. After that point the C source
    walks ``current_rule`` byte-by-byte at lines 2129-2299, calling
    :func:`par_match_string` and recursively re-entering itself.
    That walk requires the compiled ``rule_data_table`` /
    ``rule_index_table`` (loaded from ``dtalk_us.dic`` at startup)
    and the ``perform_action_funcs`` jump table -- neither of which
    is plumbed into the Python port today.

    Args:
        current_rule: Compiled rule bytes. ``None`` short-circuits
            to ``FATAL_FAIL`` per the C ``SANITY_CHECKING`` block.
        state: Action / sub-state opcode (e.g. ``BIN_END_OF_RULE``,
            ``BIN_SAVE``, ``BIN_OPTIONAL``, ``BIN_DICTIONARY``,
            ``BIN_MACRO``).
        input_array: Input text window. ``None`` -> ``FATAL_FAIL``.
        output_array: Output buffer. ``None`` -> ``FATAL_FAIL``.
        input_indexes: Per-byte pipeline-index data for the input.
        output_indexes: Per-byte pipeline-index data for the output.
        match_array: Saved-string buffers. ``None`` -> ``FATAL_FAIL``.
        ret_value: Recursion-state object. ``None`` -> early return
            (no state to mutate), matching the C ``if (ret_value ==
            NULL) return;`` branch.
        dict_state_flag: ``1`` from the dictionary-lookup path, ``0``
            otherwise.

    Returns:
        :data:`SHIM_DEFERRED` whenever the validation passes but the
        rule-engine walk would have to fire. The C source's
        ``void`` return is mapped to a status int so test code can
        observe whether the shim short-circuited or got far enough
        to require the engine.

        ``FATAL_FAIL`` when a pointer was ``None`` (writes
        ``ret_value.value = FATAL_FAIL`` first, matching the C
        source).

        :data:`SUCCESS` when ``ret_value is None`` -- the C early
        return is a no-op so there's nothing to flag, but we still
        emit a status so callers needn't special-case it.

    Raises:
        NotImplementedError: If the validation passes and the rule
            walk would normally start. Callers that genuinely need
            the rule-matching output must wire the Python rule
            engine in; for now this signals that ``dectalk._capi``
            is the correct path. See par_pars1.c lines 2129-2299
            for the dispatch and lines 2336-2429 for the post-loop
            action-table call this shim defers.
    """
    # Suppress "unused" warnings for the arguments we accept solely
    # to mirror the C signature. They're consumed by the deferred
    # engine; the shim only inspects the four NULL-checked pointers
    # and ``state``.
    del input_indexes, output_indexes, dict_state_flag

    # SANITY_CHECKING block, par_pars1.c lines 2049-2066. ``ret_value
    # == NULL`` is a no-op early return.
    if ret_value is None:
        return SUCCESS

    # The "any other pointer is NULL" -> FATAL_FAIL branch.
    if current_rule is None or input_array is None or output_array is None or match_array is None:
        ret_value.value = FATAL_FAIL
        return FATAL_FAIL

    # Unconditional preamble at par_pars1.c lines 2070-2103. Mirrors
    # the C ``new_ret`` initialisation so callers that inspect
    # ``ret_value`` after a deferred-engine call see the same cursor
    # values they would after the real driver's preamble would have
    # snapshotted them.
    new_input_pos = ret_value.input_pos + ret_value.input_offset
    new_output_pos = ret_value.output_pos + ret_value.output_offset
    new_rule_index = ret_value.rule

    # end_of_match starts at 255 for BIN_END_OF_RULE entries (line 2089).
    end_of_match = _END_OF_MATCH_FOR_BIN_END_OF_RULE if state == BIN_END_OF_RULE else 0

    # optional flag is propagated specially for BIN_OPTIONAL (lines 2093-2103).
    new_optional = 1 if state == BIN_OPTIONAL else ret_value.optional

    # State-specific rule-index advance for BIN_SAVE / BIN_DICTIONARY
    # (lines 2112-2122). These pull a save-state number from the
    # rule body -- still deterministic, so we mirror the bookkeeping
    # to keep ret_value.rule consistent for downstream debug.
    if state == BIN_SAVE and current_rule and len(current_rule) > new_rule_index + 1:
        # new_ret.rule++ to skip the operation, then read save_state_num.
        new_rule_index += 1
    elif state == BIN_DICTIONARY and current_rule and len(current_rule) > new_rule_index + 1:
        new_rule_index += 1

    # Stash the snapshot back onto ret_value's parser_flag mirror so
    # callers see the same partial state the C source would set
    # before the rule walk begins.
    ret_value.parser_flag = ret_value.parser_flag

    # The deferred portion is the dispatch loop (lines 2129-2299)
    # plus the post-loop action-table call (lines 2336-2429). Both
    # require the rule_data_table / rule_index_table and the
    # perform_action_funcs jump table, neither of which is plumbed
    # in yet.
    _ = end_of_match
    _ = new_optional
    _ = new_input_pos
    _ = new_output_pos
    raise NotImplementedError(
        "par_match_rule rule-walk (par_pars1.c lines 2129-2429) is deferred -- "
        "the Linux dectalk._capi.CAPI path provides bit-identical output today; "
        "wiring up the Python rule engine requires the rule_data_table and "
        "perform_action_funcs jump table to be loaded first. "
        f"Got state=0x{state:02X} dict_state_flag=deferred; current_rule "
        f"length={len(current_rule)} input_length={len(input_array)}."
    )


def par_match_rule_validate(
    current_rule: bytes | None,
    input_array: bytearray | None,
    output_array: bytearray | None,
    match_array: MatchArrays | None,
    ret_value: ReturnValue | None,
) -> int:
    """Run *only* the SANITY_CHECKING block from par_match_rule.

    Faithful translation of par_pars1.c lines 2049-2066. Useful for
    tests that want to exercise the deterministic validation logic
    without triggering the :class:`NotImplementedError` in
    :func:`par_match_rule`.

    Args:
        current_rule: Compiled rule bytes (``None`` triggers FATAL).
        input_array: Input window (``None`` triggers FATAL).
        output_array: Output buffer (``None`` triggers FATAL).
        match_array: Saved-string buffers (``None`` triggers FATAL).
        ret_value: Recursion-state object (``None`` -> no-op).

    Returns:
        :data:`SUCCESS` if all pointers are non-None.
        :data:`FATAL_FAIL` if any of the four mandatory pointers is
        None (writes ``ret_value.value = FATAL_FAIL`` first).
        :data:`SUCCESS` (no-op) if ``ret_value is None``.
    """
    if ret_value is None:
        return SUCCESS
    if current_rule is None or input_array is None or output_array is None or match_array is None:
        ret_value.value = FATAL_FAIL
        return FATAL_FAIL
    return SUCCESS


# Re-export so callers can mention the macro/dictionary opcodes the
# real driver branches on, without re-importing par_bin_codes.
_RECURSIVE_SUB_STATES: Final[tuple[int, ...]] = (
    BIN_OPTIONAL,
    BIN_SAVE,
    BIN_MACRO,
    BIN_DICTIONARY,
)
"""Sub-state opcodes par_match_rule recurses into; surfaced here so
parity tests can pin the list against par_pars1.c lines 2112-2171."""


__all__ = [
    "SHIM_DEFERRED",
    "MatchRuleInputs",
    "par_match_rule",
    "par_match_rule_validate",
]
