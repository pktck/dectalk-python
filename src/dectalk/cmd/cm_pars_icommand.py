"""``cm_pars_icommand`` — pull next char from the active setv slot.

Translated from ``src/dapi/src/cmd/cm_pars.c`` lines 1748-1770.

When the parser is replaying a saved command (insertflag != 0),
``cm_pars_icommand`` returns the next character of
``setv[cmd_number].cmd`` and advances ``cmd_count``. Three special
return paths:

- If the slot's ``seen`` counter saturates at 10 without
  ``cmd_count`` advancing, the parser detects a loop, resets
  state, and returns 1 (causing the caller to abort).
- If the cmd-buffer's NUL terminator is reached, ``seen`` resets,
  ``insertflag`` clears, and the return is 1 (end-of-command).
- Otherwise the current byte is returned and ``cmd_count`` advances.

The ``seen`` counter only increments at the start of replay
(``cmd_count == 0``), preventing the in-progress chars from
self-saturating.
"""

from __future__ import annotations

from dectalk.cmd.cmd_t import CmdT

_LOOP_DETECT_LIMIT = 10
_END_OF_BUFFER_SENTINEL = 1  # The C source's `return 1` for both loop + EOB.


def cm_pars_icommand(p_cmd_t: CmdT) -> int:
    """Return the next byte of the active setv slot's saved command.

    Faithful translation of:

    .. code-block:: c

        int cm_pars_icommand(PCMD_T pCmd_t) {
            if (pCmd_t->setv[pCmd_t->cmd_number].seen >= 10
                && pCmd_t->cmd_count == 0) {
                pCmd_t->setv[pCmd_t->cmd_number].seen = 0;
                pCmd_t->insertflag = 0;
                return 1;
            } else if (pCmd_t->cmd_count == 0) {
                pCmd_t->setv[pCmd_t->cmd_number].seen++;
            }
            if (pCmd_t->setv[pCmd_t->cmd_number].cmd[pCmd_t->cmd_count] == 0) {
                pCmd_t->setv[pCmd_t->cmd_number].seen = 0;
                pCmd_t->insertflag = 0;
                return 1;
            }
            pCmd_t->cmd_count++;
            return pCmd_t->setv[pCmd_t->cmd_number].cmd[pCmd_t->cmd_count - 1];
        }

    Args:
        p_cmd_t: CMD thread state with the active slot in
            ``cmd_number``, the offset in ``cmd_count``, and the
            replay flag in ``insertflag``.

    Returns:
        The next byte (0..255) from the active slot's command, or
        ``1`` on either loop-detection or end-of-buffer (the
        special return value the C source uses for both cases).
    """
    slot = p_cmd_t.setv[p_cmd_t.cmd_number]

    # Loop detection: ``seen`` saturated at start of replay.
    if slot.seen >= _LOOP_DETECT_LIMIT and p_cmd_t.cmd_count == 0:
        slot.seen = 0
        p_cmd_t.insertflag = 0
        return _END_OF_BUFFER_SENTINEL
    if p_cmd_t.cmd_count == 0:
        slot.seen += 1

    # End-of-buffer (NUL terminator).
    if p_cmd_t.cmd_count >= len(slot.cmd) or slot.cmd[p_cmd_t.cmd_count] == 0:
        slot.seen = 0
        p_cmd_t.insertflag = 0
        return _END_OF_BUFFER_SENTINEL

    p_cmd_t.cmd_count += 1
    return slot.cmd[p_cmd_t.cmd_count - 1]


__all__ = ["cm_pars_icommand"]
