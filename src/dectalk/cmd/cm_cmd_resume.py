"""``[:resume]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 964-981.

The ``[:resume]`` command interrupts a previously-issued ``[:pause]``.
On the Linux build the body reduces to:

1. ``cm_cmd_sync(phTTS) == CMD_flushing`` → return ``CMD_flushing``.
2. ``TextToSpeechResume(phTTS)`` resumes audio playback.

Both dependencies sit on Python's deferred allow-list — ``cm_cmd_sync``
is a no-op in the synchronous port and ``TextToSpeechResume`` belongs
to the C audio layer. The Python port therefore reduces to a no-op
returning :data:`CMD_success`.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def cm_cmd_resume(p_cmd_t: CmdT) -> int:
    """Resume audio playback after a ``[:pause]``.

    Faithful translation of the Linux-active branch of:

    .. code-block:: c

        int cm_cmd_resume(LPTTS_HANDLE_T phTTS) {
        #ifdef MSDOS
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            pKsd_t->pause = FALSE;
            START_SAMPCLK;
        #endif

        #if defined (WIN32) || defined (__osf__) || defined (__linux__) \
            || defined VXWORKS || defined _SPARC_SOLARIS_ \
            || defined __EMSCRIPTEN__ || defined (__APPLE__)
            if (cm_cmd_sync(phTTS) == CMD_flushing)
                return CMD_flushing;
            TextToSpeechResume(phTTS);
        #endif
            return CMD_success;
        }

    On Linux the only side-effects are an inter-thread sync barrier
    and an audio-thread resume signal — both deferred in Python's
    synchronous text path. The function reduces to ``return
    CMD_success``.

    Args:
        p_cmd_t: CMD thread state (unused — kept for signature
            parity with the surrounding handlers).

    Returns:
        :data:`CMD_success` unconditionally.
    """
    _ = p_cmd_t  # Signature parity; Linux body has no Python-visible effect.
    return CMD_success


__all__ = ["cm_cmd_resume"]
