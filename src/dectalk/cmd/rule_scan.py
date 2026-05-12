"""Rule-string position-scanning helpers from par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c``. These helpers
operate on the ASCII rule pattern bytes and advance an index past
specific structural delimiters, skipping over EXACT_CHAR (``'...'``)
and EXACT_CASE (`` `...` ``) literal blocks (which themselves
escape inner delimiters via ESCAPE_DELIM).

- :func:`par_find_conditional_number` — advance past ``cond_num``
  ``|`` separators in a conditional-replacement rule, returning the
  position of the character after the requested separator.
- :func:`par_find_end_of_rule` — advance until the next ``/``
  (STATE_PART_DELIM), skipping past literal blocks. Used to walk
  past the body of a rule action.
"""

from __future__ import annotations

from dectalk.cmd.rule_states import (
    CONDITIONAL_DELIM,
    ESCAPE_DELIM,
    EXACT_CASE_DELIM,
    EXACT_CHAR_DELIM,
    STATE_PART_DELIM,
)


def _skip_literal(current_rule: bytes, rule_p: int, terminator: int) -> int:
    """Walk ``rule_p`` past a ``terminator``-bracketed literal.

    Inner ``ESCAPE_DELIM`` characters consume one additional byte —
    that's the C source's escape mechanism for embedded quotes.

    Args:
        current_rule: Rule pattern bytes.
        rule_p: Index pointing at the byte JUST AFTER the opening
            delimiter (the first byte of the literal body).
        terminator: Closing delimiter byte (``EXACT_CHAR_DELIM`` or
            ``EXACT_CASE_DELIM``).

    Returns:
        New ``rule_p`` pointing at the closing delimiter byte.
    """
    while rule_p < len(current_rule) and current_rule[rule_p] != terminator:
        if current_rule[rule_p] == ESCAPE_DELIM:
            rule_p += 1
        rule_p += 1
    return rule_p


def par_find_conditional_number(
    current_rule: bytes | None,
    rule_p: int,
    cond_num: int,
) -> int:
    """Advance ``rule_p`` past ``cond_num`` ``|`` separators.

    Faithful translation of:

    .. code-block:: c

        int par_find_conditional_number(unsigned char *current_rule,
                                        int rule_p, int cond_num) {
            if (current_rule == NULL) return rule_p;
            while (cond_num > 0) {
                switch (current_rule[rule_p]) {
                case CONDITIONAL_DELIM:  cond_num--; break;
                case EXACT_CHAR_DELIM:   rule_p++; /* skip literal */ break;
                case EXACT_CASE_DELIM:   rule_p++; /* skip literal */ break;
                case STATE_PART_DELIM:   cond_num = -1; rule_p--; break;
                }
                rule_p++;
            }
            return rule_p;
        }

    Used by the rule engine to jump to the body of the
    ``cond_num``th conditional in a ``a|b|c|d`` style replacement.

    Args:
        current_rule: Rule pattern bytes, or ``None`` (returns
            ``rule_p`` unchanged, matching the C NULL guard).
        rule_p: Starting position, typically just past the first
            ``CONDITIONAL_DELIM`` of the conditional set.
        cond_num: Number of separators to skip past.

    Returns:
        New ``rule_p`` pointing at the byte after the requested
        separator, or just past ``STATE_PART_DELIM`` if encountered
        early.
    """
    if current_rule is None:
        return rule_p
    while cond_num > 0 and rule_p < len(current_rule):
        c = current_rule[rule_p]
        if c == CONDITIONAL_DELIM:
            cond_num -= 1
        elif c == EXACT_CHAR_DELIM:
            rule_p += 1
            rule_p = _skip_literal(current_rule, rule_p, EXACT_CHAR_DELIM)
        elif c == EXACT_CASE_DELIM:
            rule_p += 1
            rule_p = _skip_literal(current_rule, rule_p, EXACT_CASE_DELIM)
        elif c == STATE_PART_DELIM:
            cond_num = -1
            rule_p -= 1
        rule_p += 1
    return rule_p


def par_find_end_of_rule(current_rule: bytes | None, rule_p: int) -> int:
    """Advance ``rule_p`` to the position of the next ``/`` delimiter.

    Faithful translation of:

    .. code-block:: c

        int par_find_end_of_rule(unsigned char *current_rule, int rule_p) {
            if (current_rule == NULL) return rule_p;
            while (current_rule[rule_p] != STATE_PART_DELIM) {
                switch (current_rule[rule_p]) {
                case EXACT_CHAR_DELIM:   rule_p++; /* skip literal */ break;
                case EXACT_CASE_DELIM:   rule_p++; /* skip literal */ break;
                }
                rule_p++;
            }
            return rule_p;
        }

    Used to step over the action body of a rule when its conditional
    has been resolved, leaving the cursor just before the trailing
    ``/`` that separates one rule action from the next.

    Args:
        current_rule: Rule pattern bytes, or ``None`` (returns
            ``rule_p`` unchanged).
        rule_p: Starting position, typically just after the matched
            conditional-separator (``|`` or ``/``).

    Returns:
        New ``rule_p`` pointing at the byte AT the closing
        STATE_PART_DELIM (``/``).
    """
    if current_rule is None:
        return rule_p
    while rule_p < len(current_rule) and current_rule[rule_p] != STATE_PART_DELIM:
        c = current_rule[rule_p]
        if c == EXACT_CHAR_DELIM:
            rule_p += 1
            rule_p = _skip_literal(current_rule, rule_p, EXACT_CHAR_DELIM)
        elif c == EXACT_CASE_DELIM:
            rule_p += 1
            rule_p = _skip_literal(current_rule, rule_p, EXACT_CASE_DELIM)
        rule_p += 1
    return rule_p


__all__ = ["par_find_conditional_number", "par_find_end_of_rule"]
