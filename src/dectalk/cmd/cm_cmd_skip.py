"""``[:skip <mode>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1295-1329.

The ``[:skip none|email|punct|rule|all|cpg]`` command sets
``pCmd_t->skip_mode`` to one of the ``SKIP_*`` constants. Like
``cm_cmd_punct``, the keyword's index in the option table doubles
as the enum value.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_bad_value,
    CMD_success,
    SKIP_all,
    SKIP_cpg,
    SKIP_email,
    SKIP_none,
    SKIP_punct,
    SKIP_rule,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import skip_options
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match

_SKIP_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in skip_options)
_VALID_SKIP = frozenset(
    {SKIP_none, SKIP_email, SKIP_punct, SKIP_rule, SKIP_all, SKIP_cpg},
)


def cm_cmd_skip(p_cmd_t: CmdT) -> int:
    """Apply ``[:skip <mode>]`` keyword to ``pCmd_t->skip_mode``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_skip(LPTTS_HANDLE_T phTTS) {
            value = cm_util_string_match(skip_options, pCmd_t->pString[0]);
            if (value == NO_STRING_MATCH) return CMD_bad_string;
            switch (value) {
                case SKIP_none:  pCmd_t->skip_mode = SKIP_none;  break;
                case SKIP_email: pCmd_t->skip_mode = SKIP_email; break;
                case SKIP_punct: pCmd_t->skip_mode = SKIP_punct; break;
                case SKIP_rule:  pCmd_t->skip_mode = SKIP_rule;  break;
                case SKIP_all:   pCmd_t->skip_mode = SKIP_all;   break;
                case SKIP_cpg:   pCmd_t->skip_mode = SKIP_cpg;   break;
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
        doesn't correspond to a ``SKIP_*`` constant.
    """
    if not p_cmd_t.pString:
        return CMD_bad_string
    value = cm_util_string_match(_SKIP_OPTIONS_BYTES, p_cmd_t.pString[0])
    if value == NO_STRING_MATCH:
        return CMD_bad_string
    if value not in _VALID_SKIP:
        return CMD_bad_value
    p_cmd_t.skip_mode = value
    return CMD_success


__all__ = ["cm_cmd_skip"]
