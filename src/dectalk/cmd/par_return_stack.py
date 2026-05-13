"""Parser return-rule stack from par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 1285-1342.

The parser's rule engine uses a stack of rule-return values for
the GORET / GOTO control-flow primitive. The stack lives inline
as a small ``short[PAR_MAX_RETURN_LEVEL]`` array, with a separate
``short *return_level`` cursor that pre-increments on push and
pre-decrements on pop.

Two helpers manage the stack:

- :func:`par_set_return_level` — push ``go_rule`` onto the stack.
  Silently drops if the stack is at :data:`PAR_MAX_RETURN_LEVEL`.
- :func:`par_get_return_level` — pop and return the top rule, or
  fall through to ``current_rule_number + 1`` if the stack is
  empty.

The Python port models the C pointer-to-int ``return_level`` as
a single-element list ``[int]`` so the increment/decrement is
visible to the caller.
"""

from __future__ import annotations

from dectalk.cmd.par_limits import PAR_MAX_RETURN_LEVEL


def par_set_return_level(
    return_rule: list[int],
    return_level: list[int],
    go_rule: int,
) -> None:
    """Push ``go_rule`` onto the return-rule stack.

    Faithful translation of:

    .. code-block:: c

        void par_set_return_level(short *return_rule,
                                  short *return_level,
                                  short go_rule) {
            if (*return_level < PAR_MAX_RETURN_LEVEL) {
                return_rule[(*return_level)++] = go_rule;
            } else {
                printf("par_set_return_level;too many levels of gorets "
                       "throwing away %d (newline)", go_rule);
            }
        }

    Args:
        return_rule: Stack storage (list of size ``PAR_MAX_RETURN_LEVEL``).
        return_level: Single-element list holding the stack cursor.
        go_rule: Rule index to push.
    """
    if return_level[0] < PAR_MAX_RETURN_LEVEL:
        return_rule[return_level[0]] = go_rule
        return_level[0] += 1
    # Else: silently drop (matches C source — only logs a printf, no error).


def par_get_return_level(
    return_rule: list[int],
    return_level: list[int],
    current_rule_number: int,
) -> int:
    """Pop the top rule from the stack, or fall through to ``current+1``.

    Faithful translation of:

    .. code-block:: c

        short par_get_return_level(short *return_rule,
                                   short *return_level,
                                   short current_rule_number) {
            if (*return_level > 0) {
                return return_rule[--(*return_level)];
            }
            return current_rule_number + 1;
        }

    Args:
        return_rule: Stack storage.
        return_level: Single-element list holding the stack cursor.
        current_rule_number: Fall-through value if the stack is empty.

    Returns:
        The popped rule index, or ``current_rule_number + 1`` if
        the stack is empty.
    """
    if return_level[0] > 0:
        return_level[0] -= 1
        return return_rule[return_level[0]]
    return current_rule_number + 1


__all__ = ["par_get_return_level", "par_set_return_level"]
