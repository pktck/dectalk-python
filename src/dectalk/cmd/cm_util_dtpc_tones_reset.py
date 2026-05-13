"""``cm_util_dtpc_tones_reset`` helper from cm_util.c.

Translated from ``src/dapi/src/cmd/cm_util.c`` lines 647-665.

The entire active body of the function is gated by ``#ifdef MSDOS``
— on Linux the function reduces to ``return CMD_success``. The
MSDOS branch waits for the DSP to settle, resets the DSP via the
``RESET_DSP`` / ``RUN_DSP`` macros, queues a ``LAST_VOICE`` pipe
write, and clears ``tone_wait``; none of that is relevant on the
non-MSDOS Python pipeline.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success


def cm_util_dtpc_tones_reset() -> int:
    """Reset the DTMF/tone subsystem and return :data:`CMD_success`.

    Faithful translation of:

    .. code-block:: c

        int cm_util_dtpc_tones_reset(LPTTS_HANDLE_T phTTS) {
        #ifdef MSDOS
            unsigned int pipe_value;
            PCMD_T pCmd_t = phTTS->pCMDThreadData;
            PKSD_T pKsd_t = phTTS->pKernelShareData;

            if (cm_cmd_sync(phTTS) == CMD_flushing) {
                return(CMD_flushing);
            }
            sleep(pCmd_t->tone_wait);
            RESET_DSP;
            RUN_DSP;
            pipe_value = LAST_VOICE;
            cm_util_write_pipe(pKsd_t, pKsd_t->lts_pipe, &pipe_value, 1);
            pCmd_t->tone_wait = 0;
        #endif
            return(CMD_success);
        }

    The Linux build skips the entire ``#ifdef MSDOS`` block, so
    the function reduces to ``return CMD_success`` (the C body's
    only Linux-active statement). The ``phTTS`` argument is
    therefore not used in the Python port.

    Returns:
        :data:`CMD_success` (0) unconditionally on non-MSDOS
        builds.
    """
    return CMD_success


__all__ = ["cm_util_dtpc_tones_reset"]
