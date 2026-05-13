"""``par_copy_return_value`` from cmd/par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 5467-5471.

The rule-matching scaffolding uses :class:`ReturnValue` records to
thread input/output positions, recursion state, and lookahead bits
through the parser. ``par_copy_return_value`` is the field-by-field
copy helper the C source uses to save / restore those records
between recursive calls.

The C source uses ``memcpy(dest, src, sizeof(return_value_t))``;
the Python port copies each scalar field explicitly so the
``prev`` pointer keeps its identity-semantics (the C struct is
flat — Python's dataclass needs an explicit walk to mirror that).
"""

from __future__ import annotations

from dectalk.cmd.par_structs import ReturnValue


def par_copy_return_value(dest: ReturnValue, src: ReturnValue) -> None:
    """Copy all fields of ``src`` into ``dest``.

    Faithful translation of:

    .. code-block:: c

        void par_copy_return_value(preturn_value_t dest, preturn_value_t src) {
            memcpy(dest, src, sizeof(return_value_t));
        }

    Args:
        dest: Destination record; mutated in place.
        src: Source record; left untouched.
    """
    dest.input_pos = src.input_pos
    dest.input_offset = src.input_offset
    dest.output_pos = src.output_pos
    dest.output_offset = src.output_offset
    dest.rule = src.rule
    dest.value = src.value
    dest.optional = src.optional
    dest.state = src.state
    dest.parser_flag = src.parser_flag
    dest.prev = src.prev


__all__ = ["par_copy_return_value"]
