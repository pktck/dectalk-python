"""Synchronous shim for the VTM audio-sync thread entry from sync.c.

Translated from ``src/dapi/src/vtm/sync.c`` -- the ``sync_main`` thread
routine declared via ``OP_THREAD_ROUTINE(sync_main, LPTTS_HANDLE_T phTTS)``
on the Linux build.

Architectural divergence
------------------------

The C source runs ``sync_main`` as a dedicated pthread. The thread loops
forever on ``read_pipe(pKsd_t->sync_pipe, ...)``, blocking until the VTM
or higher-level layers push a one-byte control code (``SPC_type_sync``
or ``SPC_type_visual``) into the sync pipe. Each iteration either:

- waits for an absolute audio-sample boundary to play via
  :c:func:`WaitForAudioSampleToPlay` (and then signals
  ``phTTS->hSyncEvent``); or
- delivers a queued visual-notification packet (phoneme / duration
  events for lip-sync UIs) once its time-stamp sample has played.

The whole loop is glue between the audio output callback's "sample N
just hit the DAC" notifications and the application's index-mark /
phoneme callbacks. It owns no DSP state of its own.

The Python pipeline (:func:`dectalk.speak` / :func:`dectalk.to_wav`)
runs the synthesiser inline on the main thread: there is no pipe, no
background thread, and no asynchronous sample-played notifications --
:mod:`dectalk._capi` and the pure-Python fallback both produce the
entire WAV buffer in a single pass. Index marks and phoneme events
are therefore returned alongside the audio rather than streamed
through a pipe.

This module is the "synchronous shim" placeholder for that thread:
it exposes the same conceptual entry point so future async-streaming
work has somewhere to attach, but the tick is a no-op that simply
documents the divergence. The audio-sync pipe and
:c:func:`WaitForAudioSampleToPlay` are tracked in
``test_vtm_module_inventory._DEFERRED`` and will land together when
streaming output does.
"""

from __future__ import annotations

__all__ = ["sync_main_tick"]


def sync_main_tick() -> None:
    """Synchronous no-op stand-in for one iteration of ``sync_main``.

    In the C source this corresponds to a single trip through the
    ``for(;;)`` loop in ``sync_main``: read one control byte from
    ``pKsd_t->sync_pipe``, dispatch on the ``SPC_type_*`` code, and
    either block in :c:func:`WaitForAudioSampleToPlay` or post a
    visual-notification packet.

    The Python pipeline has no sync pipe -- the synthesiser produces
    its samples synchronously on the main thread and any index-mark
    callbacks fire inline -- so a "tick" has nothing to do. The
    function is preserved as a callable so tests and future
    streaming-mode work can target a stable entry point, and so the
    VTM-module inventory has a concrete Python symbol to point at
    when ``OP_THREAD_ROUTINE(sync_main, ...)`` is asked about.

    Returns:
        ``None``. The C ``OP_THREAD_RETURN`` expands to a bare
        ``return`` on Linux (the pthread routine returns ``void``),
        which maps cleanly onto Python's ``None``.
    """
    return None
