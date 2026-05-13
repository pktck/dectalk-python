"""``[:break ...]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 729-752.

The ``[:break on/off]`` command was intended to toggle
``pKsd_t->wbreak`` — a flag the kernel reads to decide whether to
insert word-boundary pauses — but the C source contains a bug:
the ``switch`` checks ``log_options`` indices 0 and 1 (which map
to ``"text"`` / ``"phonemes"``, not ``"on"`` / ``"off"`` despite
the source comments). For bit parity the Python port preserves
this behaviour exactly — ``wbreak`` only changes when the user
passes the *wrong* keywords.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_bad_string, CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import log_options
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match
from dectalk.kernel.ksd_t import KsdT

_LOG_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in log_options)

_LOG_OPT_TEXT = 0  # log_options[0] == "text" — sets wbreak=TRUE (C bug).
_LOG_OPT_PHONEMES = 1  # log_options[1] == "phonemes" — sets wbreak=FALSE.


def cm_cmd_break(p_ksd_t: KsdT, p_cmd_t: CmdT) -> int:
    """Apply each ``[:break ...]`` parameter to ``pKsd_t->wbreak``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_break(LPTTS_HANDLE_T phTTS) {
            int i, value;
            for (i = 0; i < pCmd_t->param_index; i++) {
                value = cm_util_string_match(log_options, pCmd_t->pString[i]);
                if (value == NO_STRING_MATCH) return CMD_bad_string;
                switch (value) {
                    case 0: pKsd_t->wbreak = TRUE;  break;  // "on"
                    case 1: pKsd_t->wbreak = FALSE; break;  // "off"
                }
            }
            return CMD_success;
        }

    Args:
        p_ksd_t: Kernel shared-data struct to mutate.
        p_cmd_t: CMD thread state with the parsed parameters.

    Returns:
        :data:`CMD_success` on success; :data:`CMD_bad_string` if any
        parameter doesn't match the option table.
    """
    for i in range(p_cmd_t.param_index):
        if i >= len(p_cmd_t.pString):
            break  # Defensive: parser shouldn't promise more than it has.
        value = cm_util_string_match(_LOG_OPTIONS_BYTES, p_cmd_t.pString[i])
        if value == NO_STRING_MATCH:
            return CMD_bad_string
        # The case indices below match the C source's switch — the
        # comments next to them say /* on */ and /* off */ but the
        # actual matches are "text" and "phonemes" (C-source bug).
        if value == _LOG_OPT_TEXT:
            p_ksd_t.wbreak = 1  # TRUE
        elif value == _LOG_OPT_PHONEMES:
            p_ksd_t.wbreak = 0  # FALSE
        # Other matched values are ignored (the C switch has no
        # default; "on"/"off"/"set" silently do nothing).
    return CMD_success


__all__ = ["cm_cmd_break"]
