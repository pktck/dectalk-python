"""``[:play <file>]`` (wave-file replay) handler from cmd/cmd_wav.c.

Translated from ``src/dapi/src/cmd/cmd_wav.c`` lines 193ff.

The ``[:play <file>]`` command replays an external WAV file inline
through the same audio device that the synthesizer is currently
driving. The Linux body is several hundred lines long and:

1. Calls ``cm_cmd_sync`` to flush any pending text.
2. Allocates a 16 KiB scratch buffer.
3. Calls ``WaitForLtsFlush`` / ``PA_WaitForPlayToComplete`` to
   quiesce the audio pipeline.
4. Opens the wave file via ``DTK_MMIO_OPEN`` (or AU-file fallback),
   peeks the format, optionally configures the audio device for
   8-bit mu-law, and reads/writes blocks until EOF.
5. Restores the original ``WAVEFORMATEX`` and frees its scratch.

None of those surfaces exist in the Python port:

* The synchronous Python pipeline emits WAV via
  :class:`dectalk._capi.CAPI` directly; there is no inline audio
  device to mix replayed WAVs into.
* ``cm_cmd_sync`` is a no-op in the Python pipeline.
* ``DTK_MMIO_OPEN`` / ``wave_file_open`` / ``PA_WaitForPlayToComplete``
  sit on the deferred allow-list in
  :mod:`tests.unit.test_cmd_module_inventory`.

The Python port therefore reduces to a no-op stub returning
:data:`CMD_success` so command-table dispatch doesn't break when a
``[:play ...]`` command is parsed.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def cm_cmd_play(p_cmd_t: CmdT) -> int:
    """Apply ``[:play <file>]`` — no-op stub.

    Faithful (highly abbreviated) summary of the Linux-active branch
    of cmd_wav.c's ``cm_cmd_play``:

    .. code-block:: c

        int cm_cmd_play(LPTTS_HANDLE_T phTTS) {
            // ~250 lines of WAV-file open / mu-law decode / audio
            // playback. The relevant Linux-active outline:
            if (phTTS->dwOutputState == STATE_OUTPUT_AUDIO) {
                if (cm_cmd_sync(phTTS) == CMD_flushing) return CMD_flushing;
                // allocate scratch, wait for LTS flush + PA flush,
                // open the WAV (or .au) file, read its WAVEFORMATEX,
                // possibly switch the audio device to 8-bit mu-law,
                // loop reading blocks and queueing them on
                // pAudioHandle, restore the original audio format,
                // free scratch.
            } else {
                // Speech-to-memory mode: just return success.
            }
            return CMD_success;
        }

    The Python port doesn't implement any of the inline WAV
    playback machinery — the synchronous Python TTS pipeline emits
    WAV via :class:`dectalk._capi.CAPI` and has no audio mixer to
    splice a replayed clip into. The handler is preserved so
    parsing a ``[:play ...]`` token doesn't error out at dispatch
    time.

    Args:
        p_cmd_t: CMD thread state (unused — kept for signature
            parity with the surrounding handlers; the C source
            consumes ``pCmd_t->pString[0]`` as the filename).

    Returns:
        :data:`CMD_success` unconditionally.
    """
    _ = p_cmd_t  # Deferred: no Python audio-mixer surface for inline replay.
    return CMD_success


__all__ = ["cm_cmd_play"]
