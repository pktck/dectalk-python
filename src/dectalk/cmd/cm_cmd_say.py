"""``[:say <unit>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 771-806.

The ``[:say <unit>]`` command sets ``pKsd_t->sayflag`` to one of
the ``SAY_*`` constants. The keyword is matched against the
``say_options`` table (clause / word / letter / filtered_letter /
line / syllables).

The ``letter`` and ``filtered_letter`` cases additionally trigger
a synchronisation barrier via ``cm_cmd_sync`` — if the sync says
"flushing", the command returns :data:`CMD_flushing` without
updating ``sayflag``.

The C source's sync writes to inter-thread pipes and blocks on a
semaphore. The Python port models that as a callable parameter
``sync_fn`` defaulting to "no flush in progress" so the function
is usable in single-threaded contexts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.cmd.cmd_states import CMD_bad_string, CMD_flushing, CMD_success
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import say_options
from dectalk.cmd.say_flags import (
    SAY_CLAUSE,
    SAY_FLETTER,
    SAY_LETTER,
    SAY_LINE,
    SAY_SYLLABLE,
    SAY_WORD,
)
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match
from dectalk.kernel.ksd_t import KsdT

if TYPE_CHECKING:
    from collections.abc import Callable

    SyncFn = Callable[[], int]

_SAY_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in say_options)


def _no_sync_needed() -> int:
    """Default sync callback — assumes no flush in progress."""
    return CMD_success


def cm_cmd_say(
    p_ksd_t: KsdT,
    p_cmd_t: CmdT,
    *,
    sync_fn: SyncFn = _no_sync_needed,
) -> int:
    """Apply the ``[:say <unit>]`` keyword to ``pKsd_t->sayflag``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_say(LPTTS_HANDLE_T phTTS) {
            value = cm_util_string_match(say_options, pCmd_t->pString[0]);
            if (value == NO_STRING_MATCH) return CMD_bad_string;
            switch (value) {
                case 0: pKsd_t->sayflag = SAY_CLAUSE;   break;
                case 1: pKsd_t->sayflag = SAY_WORD;     break;
                case 2:
                    if (cm_cmd_sync(phTTS) == CMD_flushing) return CMD_flushing;
                    pKsd_t->sayflag = SAY_LETTER;
                    break;
                case 3:
                    if (cm_cmd_sync(phTTS) == CMD_flushing) return CMD_flushing;
                    pKsd_t->sayflag = SAY_FLETTER;
                    break;
                case 4: pKsd_t->sayflag = SAY_LINE;     break;
                case 5: pKsd_t->sayflag = SAY_SYLLABLE; break;
            }
            return CMD_success;
        }

    Args:
        p_ksd_t: Kernel shared-data struct (target of the write).
        p_cmd_t: CMD thread state with the parsed keyword.
        sync_fn: Callable returning ``CMD_success`` or ``CMD_flushing``.
            Called before assigning ``SAY_LETTER`` / ``SAY_FLETTER``;
            if the function returns ``CMD_flushing``, ``cm_cmd_say``
            returns the same and leaves ``sayflag`` unchanged.

    Returns:
        :data:`CMD_success` on a successful keyword match;
        :data:`CMD_bad_string` if the keyword is unknown;
        :data:`CMD_flushing` if a sync is in progress when entering
        ``SAY_LETTER`` or ``SAY_FLETTER`` mode.
    """
    if not p_cmd_t.pString:
        return CMD_bad_string
    value = cm_util_string_match(_SAY_OPTIONS_BYTES, p_cmd_t.pString[0])
    if value == NO_STRING_MATCH:
        return CMD_bad_string

    direct_flags = {
        0: SAY_CLAUSE,
        1: SAY_WORD,
        4: SAY_LINE,
        5: SAY_SYLLABLE,
    }
    sync_flags = {
        2: SAY_LETTER,
        3: SAY_FLETTER,
    }

    if value in direct_flags:
        p_ksd_t.sayflag = direct_flags[value]
    elif value in sync_flags:
        if sync_fn() == CMD_flushing:
            return CMD_flushing
        p_ksd_t.sayflag = sync_flags[value]
    return CMD_success


__all__ = ["cm_cmd_say"]
