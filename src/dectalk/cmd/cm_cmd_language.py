"""``[:lang <code>]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1734-1822.

The ``[:lang <code>]`` command switches the active language. It
matches the keyword (e.g. ``english``, ``us``, ``british``, ``uk``)
against ``lang_options``, verifies the target language is fully
loaded (``lang_ready[lang] == LANG_both_ready``), then calls
:func:`default_lang` with ``ready_code=0`` to force the switch.

A ``LAST_VOICE`` token is finally written to the LTS pipe so the
LTS thread reloads its voice definitions.

The C source has two sync barriers and the pipe write, all of
which the Python port models as callable parameters so callers
can drive single-threaded test harnesses without real pipe
infrastructure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_bad_value,
    CMD_flushing,
    CMD_success,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import lang_options
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match
from dectalk.include.cmd_codes import LAST_VOICE
from dectalk.kernel.default_lang import default_lang
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_both_ready,
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    SyncFn = Callable[[], int]
    PipeWriteFn = Callable[[object, int], None]

_LANG_OPTIONS_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in lang_options)

# Index in lang_options → LANG_* code (mirrors the C switch).
_OPTION_TO_LANG: dict[int, int] = {
    0: LANG_english,
    1: LANG_british,
    2: LANG_french,
    3: LANG_german,
    4: LANG_spanish,
    5: LANG_latin_american,
    6: LANG_english,  # "us" alias
    7: LANG_british,  # "uk" alias
    8: LANG_french,  # "fr" alias
    9: LANG_german,  # "gr" alias
    10: LANG_spanish,  # "sp" alias
    11: LANG_latin_american,  # "la" alias
}


def _no_sync_needed() -> int:
    """Default sync callback — assumes no flush in progress."""
    return CMD_success


def _no_pipe_write(_pipe: object, _phone: int) -> None:
    """Default LTS-pipe sink — silently drops the LAST_VOICE signal."""


def cm_cmd_language(  # noqa: PLR0911 — faithful C-source error-fan-out.
    p_ksd_t: KsdT,
    p_cmd_t: CmdT,
    *,
    sync_fn: SyncFn = _no_sync_needed,
    lts_pipe_write: PipeWriteFn = _no_pipe_write,
) -> int:
    """Switch the active language via :func:`default_lang`.

    Faithful translation of the non-MSDOS branch of:

    .. code-block:: c

        int cm_cmd_language(LPTTS_HANDLE_T phTTS) {
            if (pCmd_t->esc_command == FALSE) {
                cmd_type = cm_util_string_match(lang_options, pCmd_t->pString[0]);
                if (cmd_type == NO_STRING_MATCH) return CMD_bad_string;
            } else
                cmd_type = pCmd_t->params[0];
            if (cm_cmd_sync(phTTS) == CMD_flushing) return CMD_flushing;
            switch (cmd_type) {
                case 0: case 6: /* english / us */
                    if (pKsd_t->lang_ready[LANG_english] == LANG_both_ready)
                        cmd_type = LANG_english;
                    else return CMD_bad_value;
                    break;
                /* ... british/french/german/spanish/latin-american branches ... */
                default: return CMD_bad_value;
            }
            if (cm_cmd_sync(phTTS) == CMD_flushing) return CMD_flushing;
            default_lang(pKsd_t, cmd_type, 0);
            pipe_value = LAST_VOICE;
            cm_util_write_pipe(pKsd_t, pKsd_t->lts_pipe, &pipe_value, 1);
            return CMD_success;
        }

    Args:
        p_ksd_t: Kernel shared-data struct.
        p_cmd_t: CMD thread state. When ``esc_command`` is FALSE, the
            keyword is parsed from ``pString[0]``; when TRUE the index
            is taken from ``params[0]`` directly.
        sync_fn: Callback returning ``CMD_success`` or ``CMD_flushing``,
            called twice (once after parse, once before default_lang).
        lts_pipe_write: Callback to dispatch the ``LAST_VOICE`` signal
            to the LTS thread.

    Returns:
        :data:`CMD_success` after a successful switch;
        :data:`CMD_bad_string` if the keyword is unknown;
        :data:`CMD_bad_value` if the target language isn't fully
        loaded; :data:`CMD_flushing` if a sync detects a flush.
    """
    if not p_cmd_t.esc_command:
        if not p_cmd_t.pString:
            return CMD_bad_string
        cmd_type = cm_util_string_match(_LANG_OPTIONS_BYTES, p_cmd_t.pString[0])
        if cmd_type == NO_STRING_MATCH:
            return CMD_bad_string
    else:
        cmd_type = p_cmd_t.params[0] if p_cmd_t.params else -1

    if sync_fn() == CMD_flushing:
        return CMD_flushing

    if cmd_type not in _OPTION_TO_LANG:
        return CMD_bad_value
    lang = _OPTION_TO_LANG[cmd_type]
    if p_ksd_t.lang_ready[lang] != LANG_both_ready:
        return CMD_bad_value

    if sync_fn() == CMD_flushing:
        return CMD_flushing

    default_lang(p_ksd_t, lang, 0)
    lts_pipe_write(p_ksd_t.lts_pipe, LAST_VOICE)
    return CMD_success


__all__ = ["cm_cmd_language"]
