"""``par_look_ahead_dictionary`` from cmd/par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3627-3650.

A small wrapper the rule engine uses to peek at the domain dictionary
without committing to a match. The C source allocates two stack
scratch buffers (``unsigned char temp_output[100]`` and
``index_data_t temp_indexes[100]``), zeroes the caller's
``ret_value`` cursor / status, calls
``par_match_rule(current_rule, BIN_DICTIONARY, ...)`` with those
scratches, and returns ``1`` when ``ret_value->value == SUCCESS``
and ``0`` otherwise.

``par_match_rule`` is the rule-engine driver and has not landed in
the Python port yet -- it remains the gating dependency for the
dictionary look-ahead path. Until then this function takes the
US-build-safe failure outcome (no dictionary match), matching the
C source's behaviour when the rule engine reports a miss.

The Python TTS pipeline never reaches this function in practice:
``dectalk._capi.CAPI`` routes ``speak()`` / ``to_wav()`` through the
C library for actual rule-driven phonetics. The Python rule engine
is only exercised by the parity tests, which do not depend on
``par_look_ahead_dictionary`` returning a hit.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import MatchArrays, ReturnValue
from dectalk.cmd.rule_states import SUCCESS


def par_look_ahead_dictionary(
    current_rule: bytes,
    input_array: bytearray,
    match_array: MatchArrays,
    ret_value: ReturnValue,
) -> int:
    """Probe the domain dictionary for a look-ahead match (stub).

    Faithful translation of:

    .. code-block:: c

        int par_look_ahead_dictionary(unsigned char *current_rule,
                                      unsigned char *input_array,
                                      pmatch_arrays_t match_array,
                                      preturn_value_t ret_value)
        {
            unsigned char temp_output[100];
            index_data_t temp_indexes[100];
            ret_value->output_pos=0;
            ret_value->output_offset=0;
            ret_value->value=SUCCESS;
            par_match_rule(current_rule, BIN_DICTIONARY, input_array,
                           temp_output, temp_indexes, temp_indexes,
                           match_array, ret_value, 1);
            if (ret_value->value == SUCCESS)
                return 1;
            return 0;
        }

    The C source first stamps ``ret_value`` with the recursion
    pre-state (``output_pos=0``, ``output_offset=0``,
    ``value=SUCCESS``) and then delegates the actual lookup to
    ``par_match_rule``. Because ``par_match_rule`` has not been
    ported yet, this stub stamps the same pre-state for parity but
    immediately returns ``0`` -- mirroring the C-style "rule did not
    match" outcome the rule engine would emit if ``par_match_rule``
    came back with a non-SUCCESS status.

    Args:
        current_rule: Compiled rule bytes (ignored by the stub).
        input_array: Input text window (ignored by the stub).
        match_array: Saved-string buffers (ignored by the stub).
        ret_value: Recursion-state object. Its ``output_pos`` /
            ``output_offset`` fields are zeroed and ``value`` is
            primed to :data:`SUCCESS`, matching the C source's
            pre-call setup.

    Returns:
        ``0`` -- no dictionary match. The real lookup is gated on
        :func:`par_match_rule`, which has not yet been ported; even
        once this function is wired in to its callers, it cannot
        return ``1`` until the rule-engine driver lands.
    """
    del current_rule, input_array, match_array
    ret_value.output_pos = 0
    ret_value.output_offset = 0
    ret_value.value = SUCCESS
    # par_match_rule(current_rule, BIN_DICTIONARY, ...) would normally
    # update ret_value.value here. The driver is not ported, so the
    # stub falls through to the C-style "no match" return.
    return 0


__all__ = ["par_look_ahead_dictionary"]
