"""Synchronous shim for the VTM packet-pump thread entry from vtmiont.c.

Translated from ``src/dapi/src/vtm/vtmiont.c`` -- the ``vtm_main`` thread
routine declared via ``OP_THREAD_ROUTINE(vtm_main, LPTTS_HANDLE_T phTTS)``
on the Linux build (when ``SINGLE_THREADED`` is not defined, which is
the default for ``libtts_us.so``).

Architectural divergence
------------------------

The C source runs ``vtm_main`` as a dedicated pthread. The thread:

1. Allocates the per-instance :c:type:`VTM_T` state struct, attaches
   it to ``phTTS->pVTMThreadData``, and signals
   ``phTTS->hMallocSuccessEvent`` so the API thread can resume.
2. Loops forever on ``read_pipe(pKsd_t->vtm_pipe, ...)``: each packet
   is one frame of synthesiser control parameters from the PH layer
   (formant targets, glottal pulse, voicing) plus the per-frame
   sample count.
3. Runs the Klatt :c:func:`speech_waveform_generator` over the frame
   to produce a buffer of 16-bit samples, then hands the buffer to
   :c:func:`OutputData` for the audio backend to play.
4. Posts visual-notification packets to ``sync_pipe`` so the sync
   thread (:func:`dectalk.vtm.sync_main.sync_main_tick`) can deliver
   them to the application at the right time.
5. Drains pending packets and tears down the VTM state on shutdown.

In other words ``vtm_main`` is the pipe-pump that connects the
phoneme-level renderer (PH) to the waveform synthesiser (VTM core)
to the audio output, all glued through pthread pipes.

The Python pipeline (:func:`dectalk.speak` / :func:`dectalk.to_wav`)
collapses that pipeline into an inline call chain on the main thread.
For the C-oracle bit-accurate path, :mod:`dectalk._capi` calls into
``libtts_us.so`` and the C code's own ``vtm_main`` thread runs
inside the shared library; the Python side never sees it. For the
pure-Python fallback path, :mod:`dectalk.hlsyn` synthesises samples
directly from the high-level synth state -- no pipe, no thread, no
:c:func:`OutputData` callback.

This module is therefore a synchronous shim that mirrors the C entry
point but does no work: it exists so future streaming-output work has
a stable place to attach, and so the VTM-module inventory has a
Python symbol to point at when ``OP_THREAD_ROUTINE(vtm_main, ...)``
is asked about. The actual synthesiser inner-loop
(:c:func:`speech_waveform_generator`), the VTM pipe drain
(:c:func:`EmptyVtmPipe`), the audio sink (:c:func:`OutputData`) and
the visual-notification dispatcher
(:c:func:`SendVisualNotification`) are all tracked separately in
``test_vtm_module_inventory._DEFERRED``.
"""

from __future__ import annotations

__all__ = ["vtm_main_tick"]


def vtm_main_tick() -> None:
    """Synchronous no-op stand-in for one iteration of ``vtm_main``.

    In the C source this corresponds to a single trip through the
    main ``vtm_main`` loop: read one VTM packet header from
    ``pKsd_t->vtm_pipe``, dispatch on the packet type (frame data,
    visual mark, end-of-utterance, etc), run the Klatt waveform
    generator over any frame data the packet brought, and push the
    resulting samples through :c:func:`OutputData`.

    The Python pipeline has no VTM pipe -- the synthesiser is invoked
    synchronously on the main thread via :mod:`dectalk._capi` (which
    in turn drives the C ``vtm_main`` inside ``libtts_us.so``) or
    via the pure-Python fallback in :mod:`dectalk.hlsyn`. A "tick"
    therefore has nothing to do. The function is preserved as a
    callable so tests and future streaming-mode work can target a
    stable entry point.

    Returns:
        ``None``. The C ``OP_THREAD_RETURN`` expands to a bare
        ``return`` on Linux (the pthread routine returns ``void``),
        which maps cleanly onto Python's ``None``.
    """
    return None
