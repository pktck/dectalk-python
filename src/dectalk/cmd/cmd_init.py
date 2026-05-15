"""CMD-thread init from cmd_init.c.

Translated from ``src/dapi/src/cmd/cmd_init.c`` lines 77-99.

The :func:`cmd_init` function initialises the CMD-thread state
when the engine boots and on every ``[:flush]`` reset. It calls
through to :func:`cm_cmd_reset_comm` for the parser-level reset
and then sets the engine-wide mode defaults (phoneme/error/
punctuation/pitch).
"""

from __future__ import annotations

from typing import Any

from dectalk.cmd.cmd_states import (
    PHONEME_OFF,
    PHONEME_SPEAK,
    STATE_NORMAL,
    ERROR_speak,
    PUNCT_some,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.parser_state import cm_cmd_reset_comm


def cmd_init(p_cmd_t: CmdT, p_ksd_t: Any, b_reset_all: bool, *, total_commands: int = 0) -> None:  # noqa: ANN401 — KSD_T placeholder
    """Initialise CMD-thread state at engine startup / flush.

    Faithful translation of:

    .. code-block:: c

        void cmd_init(LPTTS_HANDLE_T phTTS, BOOL bResetAll) {
            PCMD_T pCmd_t = phTTS->pCMDThreadData;
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            cm_cmd_reset_comm(pCmd_t, STATE_NORMAL);
            if (bResetAll) {
                pKsd_t->phoneme_mode = PHONEME_OFF | PHONEME_SPEAK;
                pCmd_t->error_mode = ERROR_speak;
                pCmd_t->punct_mode = PUNCT_some;
                pCmd_t->last_punct = 0;
                pKsd_t->pitch_delta = 35;
            }
        }

    Args:
        p_cmd_t: CMD thread-state to initialise.
        p_ksd_t: Kernel-shared-data instance (typed as ``object``
            until ``KSD_T`` is fully modelled). Must have
            mutable ``phoneme_mode`` and ``pitch_delta``
            attributes when ``b_reset_all`` is True.
        b_reset_all: If True, also reset kernel-shared engine
            mode fields (phoneme / error / punct / pitch).
        total_commands: Number of installed command-table entries
            (passed through to :func:`cm_cmd_reset_comm`).
    """
    cm_cmd_reset_comm(p_cmd_t, STATE_NORMAL, total_commands=total_commands)

    if b_reset_all:
        # Engine-wide mode defaults — these sit on the KSD_T.
        # Use setattr so this works with any duck-typed kernel-state
        # object (full struct port lands later).
        p_ksd_t.phoneme_mode = PHONEME_OFF | PHONEME_SPEAK
        p_cmd_t.error_mode = ERROR_speak
        p_cmd_t.punct_mode = PUNCT_some
        p_cmd_t.last_punct = 0
        p_ksd_t.pitch_delta = 35


def free_cmd_thread_memory(p_cmd_t: CmdT) -> None:
    """Release CMD-thread memory.

    Faithful translation of ``FreeCMDThreadMemory`` from
    ``cmd_init.c`` lines 122-144. In C this calls ``free()`` on
    the ``esc_seq`` and ``cm`` heap allocations and then on the
    ``pCmd_t`` itself.

    Python's garbage collector handles the heap automatically, so
    we just clear the scratch buffers to mirror the post-free
    invariants — anything reading ``p_cmd_t.cm`` or ``esc_seq``
    after this call must treat them as released.

    Args:
        p_cmd_t: CMD thread-state to clear.
    """
    p_cmd_t.cm = []
    p_cmd_t.esc_seq = None


FreeCMDThreadMemory = free_cmd_thread_memory

__all__ = ["FreeCMDThreadMemory", "cmd_init", "free_cmd_thread_memory"]
