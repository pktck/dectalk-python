"""Audio output queue struct (QUEUE_T) from audiodef.h.

Translated from ``src/dapi/src/include/audiodef.h`` lines 63-74.

``QUEUE_T`` is the kernel's circular buffer for queued audio samples
between the synthesiser and the audio device:

- ``pQueueStart`` points at the queue's underlying byte buffer.
- ``pQueueInput`` / ``pQueueOutput`` are the write / read cursors.
- ``iInputPosition`` / ``iOutputPosition`` are the cursor offsets.
- ``iQueueCount`` is how many bytes are currently in the queue.
- ``iQueueLength`` is the queue's total capacity in bytes.

In Python the audio data is held in :data:`pQueueStart` as a
``bytearray`` (or ``None`` until allocated). The cursor pointers
:data:`pQueueInput` / :data:`pQueueOutput` are not needed because
Python uses ``iInputPosition`` / ``iOutputPosition`` as offsets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QueueT:
    """Audio queue struct mirroring ``QUEUE_TAG`` from audiodef.h.

    Attributes:
        pQueueStart: Underlying byte buffer (``LPAUDIO_T`` = ``AUDIO_T*``).
        pQueueInput: Write-cursor pointer (offset stored in
            :data:`iInputPosition`; Python doesn't need a separate
            pointer object).
        pQueueOutput: Read-cursor pointer (see :data:`iOutputPosition`).
        iInputPosition: Write-cursor offset into ``pQueueStart``.
        iOutputPosition: Read-cursor offset into ``pQueueStart``.
        iQueueCount: Current number of bytes in the queue.
        iQueueLength: Total capacity of the queue in bytes.
    """

    pQueueStart: bytearray | None = None  # noqa: N815
    pQueueInput: object | None = None  # noqa: N815
    pQueueOutput: object | None = None  # noqa: N815
    iInputPosition: int = 0  # noqa: N815
    iOutputPosition: int = 0  # noqa: N815
    iQueueCount: int = 0  # noqa: N815
    iQueueLength: int = 0  # noqa: N815


__all__ = ["QueueT"]
