"""``[:timeout <n>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1345-1356.

The ``[:timeout <n>]`` command sets ``pCmd_t->timeout`` (and
mirrors it to ``pKsd_t->input_timeout``) from
``pCmd_t->params[0]``. When the user omits the numeric value,
``pCmd_t->defaults[0]`` is TRUE and the timeout resets to 0.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.kernel.ksd_t import KsdT


def cm_cmd_timeout(p_ksd_t: KsdT, p_cmd_t: CmdT) -> int:
    """Apply ``[:timeout <n>]`` parameter to both timeout fields.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_timeout(LPTTS_HANDLE_T phTTS) {
            if (pCmd_t->defaults[0] == TRUE)
                pCmd_t->params[0] = 0;
            pCmd_t->timeout = pCmd_t->params[0];
            pKsd_t->input_timeout = pCmd_t->timeout;
            return CMD_success;
        }

    Args:
        p_ksd_t: Kernel shared-data struct (target for ``input_timeout``).
        p_cmd_t: CMD thread state with the parsed numeric value in
            ``params[0]`` and the parser's default-flag in
            ``defaults[0]``.

    Returns:
        :data:`CMD_success` (the C source has no error path).
    """
    if p_cmd_t.defaults and p_cmd_t.defaults[0]:
        # The C source mutates pCmd_t->params[0] in place; do the same.
        if p_cmd_t.params:
            p_cmd_t.params[0] = 0
        else:
            p_cmd_t.params.append(0)
    timeout_value = p_cmd_t.params[0] if p_cmd_t.params else 0
    p_cmd_t.timeout = timeout_value
    p_ksd_t.input_timeout = timeout_value
    return CMD_success


__all__ = ["cm_cmd_timeout"]
