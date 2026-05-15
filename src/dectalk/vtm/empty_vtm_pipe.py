"""``EmptyVtmPipe`` synchronous-pipeline shim from vtmiont.c.

Translated from ``src/dapi/src/vtm/vtmiont.c`` lines 2511-2680.

The C function drains the inter-thread VTM packet pipe back into
the audio queue. It walks through every queued packet and
re-dispatches it based on the packet's ``SPC_TYPE`` (voice /
speaker-definition / sync / index-mark) under a critical-section
lock against the VTM thread reader.

The Python pipeline runs all stages synchronously on the main
thread — there is no VTM packet pipe to drain. This port is an
architectural no-op shim; it returns immediately. When a queued
pipeline lands (Phase F+ — `_capi` removal), this function would
become the queue-flush entry point.

The C source's ``bVtmDrainRequested`` / ``bVtmIsReadingPipe``
inter-thread interlock flags don't have Python equivalents either
— the synchronous pipeline can't race against itself.
"""

from __future__ import annotations


def empty_vtm_pipe() -> None:
    """Drain the VTM packet pipe — synchronous Python no-op.

    Faithful translation of the C source's architectural intent:
    return all queued VTM packets to the audio sink. On the
    synchronous Python pipeline this happens implicitly (every
    packet is processed before the next one is produced), so the
    shim returns immediately.

    The C function takes a ``PKSD_T pKsd_t`` argument it uses for
    pipe-lock acquisition; the Python port takes no arguments
    since neither the pipe nor the lock has a Python equivalent.
    """


EmptyVtmPipe = empty_vtm_pipe

__all__ = ["EmptyVtmPipe", "empty_vtm_pipe"]
