"""``flush_done`` helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 768-773.

:func:`flush_done` is called by the command processor once the
pipeline has finished flushing. It clears the ``cmd_flush`` bit
so new commands can flow again, and zeros the ``spc_sync``
semaphore counter so future ``wait_semaphore`` callers re-block
on the next sync.

On Linux this is the entirety of the C implementation — no
interrupt fences, no condvar signalling.
"""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT


def flush_done(p_ksd_t: KsdT) -> None:
    """Clear the flushing bit and reset the sync semaphore.

    Faithful translation of:

    .. code-block:: c

        void flush_done(PKSD_T pKsd_t) {
            pKsd_t->cmd_flush = false;
            pKsd_t->spc_sync.value = 0;
        }

    Args:
        p_ksd_t: Kernel shared-data struct to mutate.
    """
    p_ksd_t.cmd_flush = 0  # false
    p_ksd_t.spc_sync.value = 0


__all__ = ["flush_done"]
