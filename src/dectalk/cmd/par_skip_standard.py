"""``par_skip_standard`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 5026-5110.

Skips a standard string-match specifier in a CMD rule. The C
parser uses syntax like ``a<3>`` or ``a~<2-*>`` for character-type
repetitions; this helper advances ``ret_value.rule`` past the
``<...>`` block without doing any matching.

The standard form accepts:

- ``*``  zero-or-more (immediately before ``>``)
- ``+``  one-or-more
- ``N``  exact count
- ``N,M`` enumeration of allowed counts
- ``N-M`` inclusive count range
- ``N-*`` or ``N-+`` open-ended count range
- ``~``  negation marker
- ``NO_LOOKAHEAD`` (0x90) byte prefix

Any deviation calls :func:`par_print_rule_error` and sets
``ret_value.value`` to :data:`FATAL_FAIL`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.cmd.par_get import NO_LOOKAHEAD
from dectalk.cmd.par_number import par_convert_number_new
from dectalk.cmd.par_print_rule_error import par_print_rule_error
from dectalk.cmd.par_structs import ReturnValue
from dectalk.cmd.rule_states import FATAL_FAIL

if TYPE_CHECKING:
    from collections.abc import Callable

    EmitFn = Callable[[str], None]


def _default_emit(text: str) -> None:
    """Default emit sink — print to stdout (matches C source)."""
    print(text)


def par_skip_standard(  # noqa: PLR0911, PLR0912, PLR0915
    rule: bytes,
    ret_value: ReturnValue,
    *,
    emit: EmitFn = _default_emit,
) -> None:
    """Advance ``ret_value.rule`` past a ``<...>`` repetition specifier.

    Faithful translation of:

    .. code-block:: c

        void par_skip_standard(char *rule, preturn_value_t ret_value) {
            (ret_value->rule)++;
            if (rule[(ret_value->rule)] == NO_LOOKAHEAD)
                (ret_value->rule)++;
            if (rule[(ret_value->rule)] == '~')
                (ret_value->rule)++;
            if (rule[(ret_value->rule)] != '<') { ...FATAL_FAIL... return; }
            (ret_value->rule)++;
            while (rule[(ret_value->rule)] != '>') {
                switch (rule[(ret_value->rule)]) {
                    case '*': case '+': /* ... */
                    default:
                        par_convert_number_new(rule+(ret_value->rule), &length);
                        (ret_value->rule) += length;
                        /* check ',' / '>' / '-' separators */
                }
            }
            (ret_value->rule)++;
        }

    Args:
        rule: Full rule string the parser is walking.
        ret_value: Tracker holding the current ``rule`` offset;
            mutated in place to the position after the ``>``.
        emit: Diagnostic sink forwarded to
            :func:`par_print_rule_error` on a syntax error.
    """
    rp = ret_value.rule + 1  # Skip the type-delimiter byte.
    if rp < len(rule) and rule[rp] == NO_LOOKAHEAD:
        rp += 1
    if rp < len(rule) and rule[rp] == ord("~"):
        rp += 1
    if rp >= len(rule) or rule[rp] != ord("<"):
        ret_value.rule = rp
        par_print_rule_error(
            "no < found at the beginning of the character type in rule",
            rule,
            rp,
            emit=emit,
        )
        ret_value.value = FATAL_FAIL
        return
    rp += 1  # Skip the '<'.

    while rp < len(rule) and rule[rp] != ord(">"):
        ch = rule[rp]
        if ch == ord("*") or ch == ord("+"):
            rp += 1
            if rp >= len(rule) or rule[rp] != ord(">"):
                ret_value.rule = rp
                par_print_rule_error(
                    "> not found after * or + in rule",
                    rule,
                    rp,
                    emit=emit,
                )
                ret_value.value = FATAL_FAIL
                return
            # Loop will terminate on next iteration when it sees '>'.
            continue
        # Default: parse a count number then look for separator.
        _, length = par_convert_number_new(rule[rp:])
        rp += length
        if rp >= len(rule):
            par_print_rule_error("unexpected end of rule", rule, rp, emit=emit)
            ret_value.rule = rp
            ret_value.value = FATAL_FAIL
            return
        sep = rule[rp]
        if sep == ord(","):
            rp += 1
        elif sep == ord(">"):
            pass  # Loop terminates.
        elif sep == ord("-"):
            rp += 1
            if rp >= len(rule):
                par_print_rule_error("unexpected end of rule", rule, rp, emit=emit)
                ret_value.rule = rp
                ret_value.value = FATAL_FAIL
                return
            nxt = rule[rp]
            if nxt == ord("*") or nxt == ord("+"):
                rp += 1
                if rp >= len(rule) or rule[rp] != ord(">"):
                    par_print_rule_error(
                        "> not found after * or + in rule",
                        rule,
                        rp,
                        emit=emit,
                    )
                    ret_value.rule = rp
                    ret_value.value = FATAL_FAIL
                    return
            else:
                _, length = par_convert_number_new(rule[rp:])
                rp += length
                if rp >= len(rule) or (rule[rp] != ord(">") and rule[rp] != ord(",")):
                    par_print_rule_error(
                        "expected > or , after range in rule",
                        rule,
                        rp,
                        emit=emit,
                    )
                    ret_value.rule = rp
                    ret_value.value = FATAL_FAIL
                    return
        else:
            par_print_rule_error(
                "error in rule syntax in rule",
                rule,
                rp,
                emit=emit,
            )
            ret_value.rule = rp
            ret_value.value = FATAL_FAIL
            return

    # rp points at '>' (or end-of-rule). Step past it.
    ret_value.rule = rp + 1


__all__ = ["par_skip_standard"]
