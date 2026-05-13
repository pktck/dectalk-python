"""``[:punct <mode>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1250-1278.

The ``[:punct none|some|all|pass]`` command sets
``pCmd_t->punct_mode`` to one of the ``PUNCT_*`` constants. The
keyword matches against the ``punct_options`` table; the resulting
index doubles as the ``PUNCT_*`` enum value, so the ``switch`` is
a no-op identity assignment.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_bad_value,
    CMD_success,
    PUNCT_all,
    PUNCT_none,
    PUNCT_pass,
    PUNCT_some,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import punct_options
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match

_PUNCT_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in punct_options)
_VALID_PUNCT = frozenset({PUNCT_none, PUNCT_some, PUNCT_all, PUNCT_pass})


def cm_cmd_punct(p_cmd_t: CmdT) -> int:
    """Apply ``[:punct <mode>]`` keyword to ``pCmd_t->punct_mode``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_punct(LPTTS_HANDLE_T phTTS) {
            value = cm_util_string_match(punct_options, pCmd_t->pString[0]);
            if (value == NO_STRING_MATCH) return CMD_bad_string;
            switch (value) {
                case PUNCT_none: pCmd_t->punct_mode = PUNCT_none; break;
                case PUNCT_some: pCmd_t->punct_mode = PUNCT_some; break;
                case PUNCT_all:  pCmd_t->punct_mode = PUNCT_all;  break;
                case PUNCT_pass: pCmd_t->punct_mode = PUNCT_pass; break;
                default: return CMD_bad_value;
            }
            return CMD_success;
        }

    Args:
        p_cmd_t: CMD thread state with the parsed keyword in
            ``p_cmd_t.pString[0]``.

    Returns:
        :data:`CMD_success` on a successful keyword match;
        :data:`CMD_bad_string` if the keyword is unknown;
        :data:`CMD_bad_value` if the keyword matches but its index
        doesn't correspond to a ``PUNCT_*`` constant.
    """
    if not p_cmd_t.pString:
        return CMD_bad_string
    value = cm_util_string_match(_PUNCT_OPTIONS_BYTES, p_cmd_t.pString[0])
    if value == NO_STRING_MATCH:
        return CMD_bad_string
    if value not in _VALID_PUNCT:
        return CMD_bad_value
    p_cmd_t.punct_mode = value
    return CMD_success


__all__ = ["cm_cmd_punct"]
