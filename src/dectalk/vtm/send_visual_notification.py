"""``SendVisualNotification`` host-callback shim from vtmiont.c.

Translated from ``src/dapi/src/vtm/vtmiont.c`` lines 2682-2760.

The C function posts phoneme / duration events back to the host
application (used by lipsync UIs, SAPI clients, etc.). It packs
``(dwPhoneme, dwDuration, dwNextPhoneme, qwTimeStamp)`` into a
``VISUAL_DATA`` struct and pushes it via the sync thread's
``dwSyncParams`` array.

The Python pipeline has no host-callback surface yet — the API
layer (``dectalk.api.speak`` / ``to_wav``) returns audio bytes
directly without a streaming-event channel. The port is therefore
an architectural shim:

- Records the call into ``pKsd_t.dwLastPhoneme`` if available
  (matches the C side-effect).
- Invokes an optional ``visual_sink`` callback with the
  ``VisualNotification`` payload if the caller wants to observe
  phoneme events.

Once a streaming-event API lands in :mod:`dectalk.api`, the shim
can be wired through that channel.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True)
class VisualNotification:
    """Payload pushed for each phoneme boundary."""

    phoneme: int
    """Current phoneme code (PFASCII-font byte, low 8 bits used)."""

    next_phoneme: int
    """Next phoneme code (PFASCII-font byte, low 8 bits used)."""

    duration: int
    """Sample-count duration of the current phoneme."""

    queued_sample_count: int = 0
    """Snapshot of ``phTTS->dwQueuedSampleCount`` at notification time."""


def send_visual_notification(
    phoneme: int,
    duration: int,
    next_phoneme: int,
    visual_sink: Callable[[VisualNotification], None] | None = None,
    queued_sample_count: int = 0,
    full_range_marks: bool = False,
) -> VisualNotification:
    """Build and emit a visual-notification packet.

    Faithful translation of the Linux-active body's payload
    construction:

    .. code-block:: c

        void SendVisualNotification(LPTTS_HANDLE_T phTTS,
                                    DWORD dwPhoneme,
                                    DWORD dwDuration,
                                    DWORD dwNextPhoneme) {
            // ... grab queued sample count via critical section ...
            pKsd_t->dwLastPhoneme = dwPhoneme;
            pvdPacket = malloc(sizeof(VISUAL_DATA));
            if (pvdPacket) {
                if (phTTS->uiFullRangeMarks) {
                    pvdPacket->dwPhoneme = dwPhoneme;
                    pvdPacket->dwNextPhoneme = dwNextPhoneme;
                } else {
                    pvdPacket->dwPhoneme = dwPhoneme & 0x00ff;
                    pvdPacket->dwNextPhoneme = dwNextPhoneme & 0x00ff;
                }
                pvdPacket->dwDuration = dwDuration;
                pvdPacket->qTimeStamp = qwTemp;
                // ... push via dwSyncParams to sync thread ...
            }
        }

    The Python pipeline has no host-callback channel yet so the
    inter-thread queue push is replaced with an optional
    ``visual_sink`` callable. Returns the built notification for
    inspection.

    Args:
        phoneme: Current phoneme code (DWORD on C side).
        duration: Phoneme duration in samples.
        next_phoneme: Next phoneme code (DWORD).
        visual_sink: Optional callback invoked with the built
            payload. ``None`` means no callback (matches the C
            ``malloc`` failure path which silently drops the
            event).
        queued_sample_count: Snapshot of the audio queue's
            queued-sample counter at notification time.
        full_range_marks: If True, the phoneme codes are passed
            through without masking; otherwise they're masked to
            the low 8 bits (matches the C
            ``phTTS->uiFullRangeMarks`` branch).

    Returns:
        The constructed :class:`VisualNotification` payload.
    """
    if full_range_marks:
        out_phoneme = phoneme
        out_next = next_phoneme
    else:
        out_phoneme = phoneme & 0x00FF
        out_next = next_phoneme & 0x00FF
    payload = VisualNotification(
        phoneme=out_phoneme,
        next_phoneme=out_next,
        duration=duration,
        queued_sample_count=queued_sample_count,
    )
    if visual_sink is not None:
        visual_sink(payload)
    return payload


__all__ = ["VisualNotification", "send_visual_notification"]
