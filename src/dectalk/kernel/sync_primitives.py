"""Kernel synchronisation-primitive structs from kernel.h.

Translated from ``src/dapi/src/include/kernel.h`` lines 132-160.

Three classic kernel primitives mirroring the DECtalk Express
DTPC1/2 kernel's IPC primitives. On the Linux build these are
mostly placeholders (the engine uses pthread mutexes / condvars
via ``opthread.h`` instead) but the structs are part of the
kernel-shared-data definition so we port them for parity.

- :class:`DtSemaphore` — counting semaphore (value + waiter queue).
- :class:`QueueSemaphore` — circular linked list of waiters.
- :class:`Gate` — barrier with both block and wait queues, used to
  serialise pipe access between LTS / PH / CMD threads.

The ``queue`` / ``block_queue`` / ``wait_queue`` / ``head`` /
``tail`` / ``process`` fields originally pointed at ``PCB``
structs (process-control blocks); in the Linux build these are
unused, so we expose them as ``object | None`` placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DtSemaphore:
    """Counting semaphore (DT_SEMAPHORE in C).

    Attributes:
        value: Current semaphore count.
        queue: Process-control-block waiter queue (unused on Linux).
    """

    value: int = 0
    queue: object | None = None


@dataclass(slots=True)
class QueueSemaphore:
    """Linked-list semaphore (QUEUE_SEMAPHORE in C).

    Attributes:
        head: Head of the waiter queue (next-pointer to a ``QueueSemaphore``).
        tail: Tail of the waiter queue.
        process: Pointer to the calling PCB.
    """

    head: object | None = None
    tail: object | None = None
    process: object | None = None


@dataclass(slots=True)
class Gate:
    """Two-queue barrier (GATE in C).

    Attributes:
        value: Gate counter / signal value.
        state: Gate state (open/closed/transit).
        block_queue: PCB queue for blocked processes.
        wait_queue: PCB queue for waiting processes.
    """

    value: int = 0
    state: int = 0
    block_queue: object | None = None
    wait_queue: object | None = None


__all__ = ["DtSemaphore", "Gate", "QueueSemaphore"]
