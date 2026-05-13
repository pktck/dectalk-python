r"""``[:loadv N text]`` command handler from cmd/cm_copt.c.

Architectural shim for ``src/dapi/src/cmd/cm_copt.c`` lines 1435-1480.

The C body reads characters from the inter-thread ``cmd_pipe`` until
``]`` is seen (max 60 chars including the trailing NUL), then stores
the resulting string at ``pCmd_t->setv[cmd_number].cmd``. In the
Python port the parser already has the full command body in hand --
there is no inter-thread pipe -- so we expose the validation and
post-condition surface as a small helper that the higher-level
parser machinery can call.

Faithful translation of:

.. code-block:: c

    int cm_cmd_loadv(LPTTS_HANDLE_T phTTS) {
        PCMD_T pCmd_t = phTTS->pCMDThreadData;
        unsigned char temp[60];
        int j = 0;
        int flag = 1;

        if (pCmd_t->insertflag) {
            return CMD_bad_param;
        }
        if ((pCmd_t->params[0]) < 0 || pCmd_t->params[0] > 9)
            return CMD_bad_value;
        pCmd_t->cmd_count = 0;
        pCmd_t->cmd_number = pCmd_t->params[0];
        while (flag) {
            read_pipe(pKsd_t->cmd_pipe, &temp[j], 1);
            if (temp[j] == ']')
                flag = 0;
            j++;
            if (j >= sizeof(temp) - 1) {
                return CMD_bad_param;
            }
        }
        temp[j] = '\0';
        strcpy(pCmd_t->setv[pCmd_t->cmd_number].cmd, temp);
        return CMD_success;
    }
"""

from __future__ import annotations

from dataclasses import dataclass

from dectalk.cmd.cmd_states import CMD_bad_param, CMD_bad_value, CMD_success

# ``temp[60]`` in C -- one slot is reserved for the trailing NUL, and the
# C loop reads characters until ``j >= sizeof(temp) - 1`` which is 59.
# Therefore the longest payload (including the terminating ``]``) is 59
# bytes; anything longer returns ``CMD_bad_param``.
_LOADV_MAX_BODY_LEN = 59

_LOADV_MIN_SLOT = 0
_LOADV_MAX_SLOT = 9


@dataclass
class LoadvResult:
    """Outcome of the ``[:loadv N text]`` command.

    Attributes:
        voice_slot: The voice slot index (0..9) that was targeted. On
            failure this is still set to the input slot for callers that
            want to inspect what was attempted.
        body: The body bytes with the trailing ``]`` stripped. Empty on
            failure.
        status: One of :data:`CMD_success`, :data:`CMD_bad_value`,
            :data:`CMD_bad_param`.
    """

    voice_slot: int
    body: bytes
    status: int


def cm_cmd_loadv(slot: int, body: bytes, insert_flag: bool) -> LoadvResult:
    """Validate a ``[:loadv N text]`` invocation.

    Args:
        slot: The voice slot index from the loaded ``[:loadv <slot>]``
            argument. Must be in 0..9 (inclusive).
        body: The terminator-included loaded body bytes -- the parser
            should have collected characters from the input up to and
            including the closing ``]``. The terminator byte is
            stripped from :attr:`LoadvResult.body` on success.
        insert_flag: The C ``pCmd_t->insertflag``. When truthy the C
            body refuses with :data:`CMD_bad_param` -- ``[:loadv]``
            can't be called from ``[:setv]`` replay.

    Returns:
        A :class:`LoadvResult` describing the outcome.
    """
    # ``loadv can't be called from setv`` (cm_copt.c comment).
    if insert_flag:
        return LoadvResult(voice_slot=slot, body=b"", status=CMD_bad_param)

    if slot < _LOADV_MIN_SLOT or slot > _LOADV_MAX_SLOT:
        return LoadvResult(voice_slot=slot, body=b"", status=CMD_bad_value)

    # The C loop reads up to 59 bytes including the closing ']'. The
    # 60th byte position is reserved for the trailing NUL. Any body
    # that grows past 59 bytes triggers CMD_bad_param.
    if len(body) > _LOADV_MAX_BODY_LEN:
        return LoadvResult(voice_slot=slot, body=b"", status=CMD_bad_param)

    # Strip the trailing ``]`` if present -- the C body keeps it in
    # ``temp`` and then NUL-terminates, but the stored ``setv[].cmd``
    # contents already include that ``]`` byte. The Python port
    # exposes the body without the terminator so callers can re-use
    # it without re-parsing.
    stripped = body[:-1] if body.endswith(b"]") else body

    return LoadvResult(voice_slot=slot, body=stripped, status=CMD_success)


__all__ = ["LoadvResult", "cm_cmd_loadv"]
