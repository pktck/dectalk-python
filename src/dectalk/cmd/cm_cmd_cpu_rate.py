"""``[:cpu-rate <n>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1372-1383.

On MSDOS the ``[:cpu-rate <n>]`` command calls ``module_clocks(n)``
to set the CPU clock divider. On Linux / Windows / etc. the entire
body is ``#ifdef MSDOS`` so the function is a no-op that always
returns :data:`CMD_success`.

The Python port targets the Linux build (libtts_us.so) so it
matches the no-op behaviour.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def cm_cmd_cpu_rate(p_cmd_t: CmdT) -> int:
    """Always return :data:`CMD_success` on non-MSDOS builds.

    Faithful translation of the non-MSDOS branch of:

    .. code-block:: c

        int cm_cmd_cpu_rate(LPTTS_HANDLE_T phTTS) {
        #ifdef MSDOS
            if (pCmd_t->defaults[0] == TRUE) pCmd_t->params[0] = 10;
            if (pCmd_t->params[0] <= 0 || pCmd_t->params[0] > 25)
                return CMD_bad_value;
            module_clocks(pCmd_t->params[0]);
        #endif
            return CMD_success;
        }

    Args:
        p_cmd_t: CMD thread state (unused — kept for signature parity).

    Returns:
        :data:`CMD_success` unconditionally.
    """
    _ = p_cmd_t  # Linux build ignores its argument — signature parity.
    return CMD_success


__all__ = ["cm_cmd_cpu_rate"]
