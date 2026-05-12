"""Command-table entry struct from cm_data.h.

Translated from ``src/dapi/src/cmd/cm_data.h``. ``dtpc_command`` is
one row in the global command-name dispatch table: command name,
parameter format string, parameter count, escape-value, and a
function-pointer to the handler.

The Python port uses ``Callable[..., int]`` for the handler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True)
class DtpcCommand:
    """One row in the CMD parser's command dispatch table.

    Faithful translation of:

    .. code-block:: c

        struct dtpc_command {
            unsigned char *c_name;         // command string name
            unsigned char *c_format;       // format of command params
            int           n_params;        // number of params
            unsigned int  esc_value;       // value for escaped version
            int (*c_routine)(LPTTS_HANDLE_T);  // handler fn
        };

    The C source's function pointer becomes a Python callable;
    callers should respect the ``int`` return convention (one of
    the :class:`~dectalk.cmd.cmd_states.CMD_*` codes).

    Attributes:
        c_name: Command name (bytes — e.g. ``b"rate"``).
        c_format: Parameter format string (bytes — e.g. ``b"n"``).
        n_params: Expected number of parameters.
        esc_value: Pre-encoded escape-sequence value.
        c_routine: Handler function. ``None`` for unimplemented
            entries.
    """

    c_name: bytes = b""
    c_format: bytes = b""
    n_params: int = 0
    esc_value: int = 0
    c_routine: Callable[..., int] | None = None


__all__ = ["DtpcCommand"]
