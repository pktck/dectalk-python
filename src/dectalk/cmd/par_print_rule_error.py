"""``par_print_rule_error`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 5434-5448.

A small debug-print helper the rule-matching scaffolding calls
when it detects a malformed rule. The C source writes to stdout
(``printf``); the Python port writes to a configurable sink so
the harness / tests can verify the diagnostic without polluting
their own output.

Caller convention: ``par_print_rule_error`` only emits diagnostic
text — it never mutates the return-value record. Setting
``ret_value->value = FATAL_FAIL`` is the caller's job.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    EmitFn = Callable[[str], None]


def _print_to_stdout(text: str) -> None:
    """Default emit sink — prints to stdout, matching the C source."""
    print(text)


def par_print_rule_error(
    message: str,
    current_rule: bytes,
    pos: int,
    *,
    emit: EmitFn = _print_to_stdout,
) -> None:
    r"""Report a malformed-rule diagnostic.

    Faithful translation of:

    .. code-block:: c

        void par_print_rule_error(char *message,
                                  unsigned char *current_rule,
                                  int pos) {
            int i;
            printf("%s\n", message);
            printf("error in rule at position %d\n", pos);
            printf("rule, %s\n", current_rule);
            printf("      ");
            for (i = 0; i < pos; i++) printf(" ");
            printf("^\n");
        }

    Args:
        message: Diagnostic message.
        current_rule: The rule string that triggered the error.
        pos: Byte offset within ``current_rule`` where the error
            was detected.
        emit: Sink for the diagnostic text. Each emit call carries
            one logical line (newline stripped). Defaults to
            ``print(line)``.
    """
    emit(message)
    emit(f"error in rule at position {pos}")
    emit(f"rule, {current_rule.decode('latin-1', errors='replace')}")
    # Caret line: 6 leading spaces (the C source's "      "), then ``pos``
    # spaces, then '^'.
    emit("      " + " " * pos + "^")


__all__ = ["par_print_rule_error"]
