"""``par_build_string_from_rule`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3994-4191.

Materialises a replacement / insertion string from a compiled rule.
The function walks the compiled rule from ``ret_value.rule`` up to a
state-controlled end position (``current_rule[in_rule_index + 2]``)
and emits each ``BIN_EXACT`` / ``BIN_RESTORE`` / ``BIN_HEXADECIMAL``
segment into ``buf``. It also handles the conditional-replace
(``$1`` / ``$2`` ...) opcode which selects one of several
alternative output strings based on a digit observed in the matched
input range.

The GERMAN_COMPOUND_NOUNS branch is the one that lives on the Linux
build (see ``_LINUX_DEFINED`` in
``tests/unit/test_cmd_module_inventory.py``). On that variant the
conditional-replace switch is keyed on ``state & BIN_OPERATION_MASK``
and the ``BIN_INSERT`` case is split by the ``BIN_BEFORE_FLAG`` /
``BIN_AFTER_FLAG`` bits to dispatch between the "look at first char
of range" vs "look at last char of range" probes.
"""

from __future__ import annotations

from dectalk.cmd.par_bin_codes import (
    BIN_AFTER_FLAG,
    BIN_BEFORE_FLAG,
    BIN_CONDITIONAL_REPLACE,
    BIN_END_OF_RULE,
    BIN_EXACT,
    BIN_HEXADECIMAL,
    BIN_INSERT,
    BIN_OPERATION_MASK,
    BIN_RESTORE,
)
from dectalk.cmd.par_number import par_convert_number_new2
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL


def par_build_string_from_rule(  # noqa: PLR0912, PLR0915 — mirrors the C source's nested branching
    current_rule: bytes,
    buf: bytearray,
    output_array: bytearray,
    match_array: MatchArrays,
    ret_value: ReturnValue,
    range_value: RangeValue,
    state: int,
    length: list[int],
    in_rule_index: int,
) -> bytearray | None:
    r"""Build the replacement / insert string from ``current_rule`` into ``buf``.

    Faithful translation of:

    .. code-block:: c

        unsigned char *par_build_string_from_rule(
                unsigned char *current_rule, unsigned char *buf,
                unsigned char *output_array, pmatch_arrays_t match_array,
                preturn_value_t ret_value, prange_value_t range_value,
                int state, int *length, int in_rule_index) {
            int is_cond=0, cond_num=0, rule_p, buf_ind=0, match_l=0, match_num;
            U8 end_of_action, end_of_build;

            if (ret_value==NULL) return NULL;
            if (current_rule==NULL || buf==NULL || match_array==NULL ||
                state==BIN_END_OF_RULE || length==NULL) {
                ret_value->value=FATAL_FAIL;
                return NULL;
            }

            rule_p = ret_value->rule;
            end_of_action = current_rule[in_rule_index+2];
            end_of_build = end_of_action;
            buf[0]='\0';

            if (current_rule[in_rule_index] & BIN_CONDITIONAL_REPLACE) {
                is_cond = -1;
                switch (state & BIN_OPERATION_MASK) {
                case BIN_INSERT:
                    if (state & BIN_BEFORE_FLAG) {
                        if (range_value->range_set==2)
                            cond_num = range_value->start;
                        else {
                            cond_num = output_array[ret_value->output_pos]-'0';
                            if (cond_num<0 || cond_num>9) cond_num=0;
                        }
                    }
                    if (state & BIN_AFTER_FLAG) {
                        if (range_value->range_set==2)
                            cond_num = range_value->start;
                        else {
                            cond_num = output_array[
                                ret_value->output_pos
                                + ret_value->output_offset - 1] - '0';
                            if (cond_num<0 || cond_num>9) cond_num=0;
                        }
                    }
                    /* intentional fallthrough to default */
                default:
                    if (range_value->range_set==2)
                        cond_num = range_value->start;
                    else {
                        output_array[ret_value->output_offset
                                     + ret_value->output_pos] = '\0';
                        cond_num = par_convert_number_new2(
                            output_array + ret_value->output_pos);
                        if (range_value->range_set==1)
                            cond_num -= range_value->start;
                    }
                }
                if (cond_num > current_rule[in_rule_index+3]) cond_num = 0;
                if (cond_num==0)
                    end_of_build = current_rule[in_rule_index+4];
                else {
                    if (cond_num == current_rule[in_rule_index+3]) {
                        rule_p = current_rule[in_rule_index+3+cond_num]+1;
                        end_of_build = current_rule[in_rule_index+2];
                    } else {
                        rule_p = current_rule[in_rule_index+3+cond_num]+1;
                        end_of_build = current_rule[in_rule_index+4+cond_num];
                    }
                }
            }

            while (rule_p <= end_of_build) {
                switch (current_rule[rule_p] & BIN_OPERATION_MASK) {
                case BIN_EXACT:
                    rule_p++;
                    match_l = current_rule[rule_p];
                    rule_p++;
                    memcpy(&buf[buf_ind], &current_rule[rule_p], match_l);
                    rule_p += match_l;
                    buf_ind += match_l;
                    break;
                case BIN_RESTORE:
                    rule_p++;
                    match_num = current_rule[rule_p];
                    match_l = match_array->array_lengths[match_num];
                    memcpy(buf+buf_ind, match_array->array[match_num], match_l);
                    buf_ind += match_l;
                    rule_p++;
                    break;
                case BIN_HEXADECIMAL:
                    rule_p++;
                    buf[buf_ind] = current_rule[rule_p];
                    buf_ind++;
                    rule_p++;
                    break;
                default:
                    ret_value->value = FATAL_FAIL;
                    return NULL;
                }
            }
            buf[buf_ind] = '\0';
            *length = buf_ind;
            ret_value->rule = end_of_action + 1;
            return buf;
        }

    The GERMAN_COMPOUND_NOUNS branch is the active one on Linux (it
    is in :data:`tests.unit.test_cmd_module_inventory._LINUX_DEFINED`).
    On that variant the conditional switch is keyed on
    ``state & BIN_OPERATION_MASK`` and the BIN_INSERT case is split
    by the ``BIN_BEFORE_FLAG`` / ``BIN_AFTER_FLAG`` bits. There is no
    explicit ``break`` between the BIN_INSERT block and the
    ``default`` block on this variant — the comment in the C source
    explicitly calls that out (``it is intended to not have a break
    after the case for BIN_INSERT``). The Python port mirrors this
    fallthrough by structuring the if/elif as a guarded sequence with
    a final unconditional default branch that re-runs the
    range-set/digit-scan when neither flag is set.

    Args:
        current_rule: Compiled rule bytes.
        buf: Destination byte buffer for the built string. Mutated in
            place — caller pre-allocates at least 100 bytes (the C
            stack-allocated size for the callers ``par_replace_string``
            / ``par_insert_string*``) or 10 bytes (for
            ``par_status_string``).
        output_array: Output buffer (read for conditional-digit
            sniffing). The conditional branch writes a NUL byte at
            ``output_pos + output_offset`` to terminate the digit run
            for :func:`par_convert_number_new2` — mirrors the C
            source's pre-conversion termination.
        match_array: ``$N`` save slot collection (read for BIN_RESTORE).
        ret_value: Parser cursors; ``rule`` advances to
            ``end_of_action + 1`` on success; ``value`` is set to
            :data:`FATAL_FAIL` on a bad opcode.
        range_value: Range-match state (``range_set`` selects whether
            the conditional uses the range's ``start`` directly or
            scans the matched output as decimal digits).
        state: ``BIN_*`` action-state code (``BIN_REPLACE`` /
            ``BIN_INSERT`` (with optional ``BIN_BEFORE_FLAG`` or
            ``BIN_AFTER_FLAG``) / ``BIN_AFTER`` / ``BIN_BEFORE`` /
            ``BIN_STATUS``).
        length: 1-element list used as an out-parameter for the
            written byte count (Python equivalent of ``int *``).
        in_rule_index: Index of the action descriptor inside
            ``current_rule`` (the parent rule's ``BIN_REPLACE`` / etc.
            opcode position).

    Returns:
        ``buf`` on success, ``None`` on a fatal error (also sets
        ``ret_value.value = FATAL_FAIL``).
    """
    # Sanity check mirroring the SANITY_CHECKING block in the C source.
    # The C null-pointer checks are unreachable in Python (type system
    # rules out None), so only the state-validity guard remains.
    if state == BIN_END_OF_RULE:
        ret_value.value = FATAL_FAIL
        return None

    cond_num = 0
    buf_ind = 0
    rule_p = ret_value.rule
    end_of_action = current_rule[in_rule_index + 2]
    end_of_build = end_of_action

    # Clear buf just in case (the C source: `buf[0] = '\0';`).
    if len(buf) > 0:
        buf[0] = 0

    if current_rule[in_rule_index] & BIN_CONDITIONAL_REPLACE:
        # is_cond = -1 in the C source — left as a marker, never read,
        # so the Python port omits the assignment.
        operation = state & BIN_OPERATION_MASK
        # GERMAN_COMPOUND_NOUNS branch: switch(state & BIN_OPERATION_MASK).
        # The case BIN_INSERT block uses the BIN_BEFORE_FLAG / BIN_AFTER_FLAG
        # bits in `state` to choose between two sub-paths; if neither is
        # set, the BIN_INSERT case falls through to the default block.
        handled = False
        if operation == BIN_INSERT:
            if state & BIN_BEFORE_FLAG:
                # Read the first character in the output range.
                if range_value.range_set == 2:  # noqa: PLR2004 — mirrors C constant
                    cond_num = range_value.start
                else:
                    cond_num = output_array[ret_value.output_pos] - ord("0")
                    if cond_num < 0 or cond_num > 9:  # noqa: PLR2004 — digit range
                        cond_num = 0
                handled = True
            if state & BIN_AFTER_FLAG:
                # Convert the last character in the range.
                if range_value.range_set == 2:  # noqa: PLR2004 — mirrors C constant
                    cond_num = range_value.start
                else:
                    cond_num = output_array[
                        ret_value.output_pos + ret_value.output_offset - 1
                    ] - ord("0")
                    if cond_num < 0 or cond_num > 9:  # noqa: PLR2004 — digit range
                        cond_num = 0
                handled = True
        if not handled:
            # Default branch: scan the matched output as a decimal number.
            if range_value.range_set == 2:  # noqa: PLR2004 — mirrors C constant
                cond_num = range_value.start
            else:
                # Terminate the range with NUL so par_convert_number_new2
                # stops scanning at the boundary (mirrors the C source).
                term_pos = ret_value.output_offset + ret_value.output_pos
                while len(output_array) <= term_pos:
                    output_array.append(0)
                output_array[term_pos] = 0
                cond_num = par_convert_number_new2(bytes(output_array[ret_value.output_pos :]))
                if range_value.range_set == 1:
                    cond_num -= range_value.start

        if cond_num > current_rule[in_rule_index + 3]:
            cond_num = 0

        if cond_num == 0:
            end_of_build = current_rule[in_rule_index + 4]
        elif cond_num == current_rule[in_rule_index + 3]:
            rule_p = current_rule[in_rule_index + 3 + cond_num] + 1
            end_of_build = current_rule[in_rule_index + 2]
        else:
            rule_p = current_rule[in_rule_index + 3 + cond_num] + 1
            end_of_build = current_rule[in_rule_index + 4 + cond_num]

    while rule_p <= end_of_build:
        # Build the string until the end_of_build marker.
        op = current_rule[rule_p] & BIN_OPERATION_MASK
        if op == BIN_EXACT:
            # An exact string was found: the next byte holds the length,
            # followed by `match_l` literal characters.
            rule_p += 1
            match_l = current_rule[rule_p]
            rule_p += 1
            # Grow buf if needed.
            while len(buf) < buf_ind + match_l:
                buf.append(0)
            buf[buf_ind : buf_ind + match_l] = current_rule[rule_p : rule_p + match_l]
            rule_p += match_l
            buf_ind += match_l
        elif op == BIN_RESTORE:
            # A $# sequence: the next byte holds the match-array slot index.
            rule_p += 1
            match_num = current_rule[rule_p]
            match_l = match_array.array_lengths[match_num]
            while len(buf) < buf_ind + match_l:
                buf.append(0)
            buf[buf_ind : buf_ind + match_l] = match_array.array[match_num][:match_l]
            buf_ind += match_l
            rule_p += 1
        elif op == BIN_HEXADECIMAL:
            # A hexadecimal value (already decoded into a single byte by
            # the rule compiler) was found.
            rule_p += 1
            while len(buf) <= buf_ind:
                buf.append(0)
            buf[buf_ind] = current_rule[rule_p]
            buf_ind += 1
            rule_p += 1
        else:
            # Unrecognised delimiter -- fatal error.
            ret_value.value = FATAL_FAIL
            return None

    # The end of the rule has been hit.
    while len(buf) <= buf_ind:
        buf.append(0)
    buf[buf_ind] = 0
    length[0] = buf_ind
    ret_value.rule = end_of_action + 1
    return buf


__all__ = ["par_build_string_from_rule"]
