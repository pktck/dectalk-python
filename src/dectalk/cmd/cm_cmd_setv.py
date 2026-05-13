"""``[:setv <slot>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1399-1420.

The ``[:setv <slot>]`` command tells the parser to execute the
saved command stored in ``pCmd_t->setv[slot]`` (where ``slot`` is
0..9). It sets ``insertflag = 1`` to ask the next parse cycle to
replay the saved command string. On the ``VOCAL`` build the
``insertflag`` becomes 2 instead (per BATS#638); the Python port
follows the standard non-``VOCAL`` build's value of 1.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_bad_value, CMD_success
from dectalk.cmd.cmd_t import CmdT

_SETV_MAX_SLOT = 9


def cm_cmd_setv(p_cmd_t: CmdT) -> int:
    """Apply ``[:setv <slot>]`` to ``pCmd_t->cmd_number`` / ``insertflag``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_setv(LPTTS_HANDLE_T phTTS) {
            if ((pCmd_t->params[0]) < 0 || pCmd_t->params[0] > 9)
                return CMD_bad_value;
            pCmd_t->cmd_count = 0;
            pCmd_t->cmd_number = pCmd_t->params[0];
            pCmd_t->insertflag = 1;  /* (or 2 on VOCAL) */
            return CMD_success;
        }

    Args:
        p_cmd_t: CMD thread state with the slot number in
            ``p_cmd_t.params[0]``.

    Returns:
        :data:`CMD_success` if the slot is valid (0..9);
        :data:`CMD_bad_value` otherwise.
    """
    slot = p_cmd_t.params[0] if p_cmd_t.params else -1
    if slot < 0 or slot > _SETV_MAX_SLOT:
        return CMD_bad_value
    p_cmd_t.cmd_count = 0
    p_cmd_t.cmd_number = slot
    p_cmd_t.insertflag = 1  # 2 on VOCAL build; standard build uses 1.
    return CMD_success


__all__ = ["cm_cmd_setv"]
