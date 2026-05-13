"""``[:error <mode>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 826-854.

The ``[:error <ignore|text|escape|speak|tone>]`` command sets
``pCmd_t->error_mode`` to one of the ``ERROR_*`` constants. The
parser reads ``pCmd_t->p_string[0]``, string-matches it against
the ``error_options`` table, and stores the index-derived mode.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_success,
    ERROR_escape,
    ERROR_ignore,
    ERROR_speak,
    ERROR_text,
    ERROR_tone,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import error_options
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match

_ERROR_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in error_options)


def cm_cmd_error(p_cmd_t: CmdT) -> int:
    """Apply the ``[:error <mode>]`` keyword to ``pCmd_t->error_mode``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_error(LPTTS_HANDLE_T phTTS) {
            value = cm_util_string_match(error_options, pCmd_t->pString[0]);
            if (value == NO_STRING_MATCH) return CMD_bad_string;
            switch (value) {
                case 0: pCmd_t->error_mode = ERROR_ignore; break;
                case 1: pCmd_t->error_mode = ERROR_text;   break;
                case 2: pCmd_t->error_mode = ERROR_escape; break;
                case 3: pCmd_t->error_mode = ERROR_speak;  break;
                case 4: pCmd_t->error_mode = ERROR_tone;   break;
            }
            return CMD_success;
        }

    Args:
        p_cmd_t: CMD thread state. ``p_cmd_t.pString[0]`` must
            be one of "ignore", "text", "escape", "speak", "tone".

    Returns:
        :data:`CMD_success` on a successful keyword match;
        :data:`CMD_bad_string` if the keyword is unknown.
    """
    if not p_cmd_t.pString:
        return CMD_bad_string
    value = cm_util_string_match(_ERROR_OPTIONS_BYTES, p_cmd_t.pString[0])
    if value == NO_STRING_MATCH:
        return CMD_bad_string
    mode_map = {
        0: ERROR_ignore,
        1: ERROR_text,
        2: ERROR_escape,
        3: ERROR_speak,
        4: ERROR_tone,
    }
    if value in mode_map:
        p_cmd_t.error_mode = mode_map[value]
    return CMD_success


__all__ = ["cm_cmd_error"]
