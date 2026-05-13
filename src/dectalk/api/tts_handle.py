# ruff: noqa: N815 — preserve C-source mixedCase field names (pKernelShareData, etc.)
"""Full DECtalk TTS engine handle struct (TTS_HANDLE_T) from tts.h.

Translated from ``src/dapi/src/api/tts.h`` lines 242-..

``TTS_HANDLE_TAG`` is the top-level engine handle the public
``TextToSpeech*`` API hands out. It aggregates all per-thread
state pointers plus the queue / lifecycle handles.

The 5 thread-data pointers are the major sub-states:

- :attr:`pKernelShareData` — :class:`dectalk.kernel.share_data`
  (the engine-wide KSD).
- :attr:`pCMDThreadData` — :class:`dectalk.cmd.cmd_t.CmdT`.
- :attr:`pLTSThreadData` — :class:`dectalk.lts.lts_t.LtsT`.
- :attr:`pPHThreadData` — :class:`dectalk.ph.dph_t.DphT`.
- :attr:`pVTMThreadData` — VTM thread state (no port yet).

Linux-only fields (the ``HEVENT_T`` / ``HTHREAD_T`` group inside
``__linux__``) are modelled as ``object | None`` placeholders;
they point at pthread mutex / condvar primitives the engine never
actually uses through the Python port.

The dectalk.ph.tts_handle.TtsHandle (2 fields) is the slim
sub-struct PH-internal code uses; this is the full handle the
public API exposes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TtsHandleFull:
    """Full ``TTS_HANDLE_T`` struct mirroring ``api/tts.h``.

    Attributes:
        pKernelShareData: Pointer to the engine-wide ``KSD_T`` block.
        pCMDThreadData: Pointer to the per-thread ``CMD_T`` instance state.
        pLTSThreadData: Pointer to the per-thread ``LTS_T`` instance state.
        pVTMThreadData: Pointer to the per-thread VTM instance state.
        pPHThreadData: Pointer to the per-thread ``DPH_T`` instance state.
        hMallocSuccessEvent: Linux event handle (pthread condvar).
        hThread_TXT: Text-input thread handle.
        hThread_CMD: CMD thread handle.
        hThread_LTS: LTS thread handle.
        hThread_PH: PH thread handle.
        hThread_VTM: VTM thread handle.
        hThread_SYNC: Sync thread handle.
        hSyncEvent: Sync event handle.
        hNotEmptyingVtmPipeEvent: Event handle for VTM-pipe drain.
        hTextInQueueEvent: Text-queue event handle.
        uiTextThreadExit: Text-thread exit flag.
        uiThreadError: Thread error flag.
        uiQueuedCharacterCount: Number of characters queued for processing.
        uiCurrentMsgNumber: Current message sequence number.
    """

    # Per-thread state pointers (the main slots).
    pKernelShareData: object | None = None
    pCMDThreadData: object | None = None
    pLTSThreadData: object | None = None
    pVTMThreadData: object | None = None
    pPHThreadData: object | None = None

    # Linux event / thread handles (placeholders).
    hMallocSuccessEvent: object | None = None
    hThread_TXT: object | None = None
    hThread_CMD: object | None = None
    hThread_LTS: object | None = None
    hThread_PH: object | None = None
    hThread_VTM: object | None = None
    hThread_SYNC: object | None = None
    hSyncEvent: object | None = None
    hNotEmptyingVtmPipeEvent: object | None = None
    hTextInQueueEvent: object | None = None

    # Linux-specific exit / error flags.
    uiTextThreadExit: int = 0
    uiThreadError: int = 0

    # Queue / message counters.
    uiQueuedCharacterCount: int = 0
    uiCurrentMsgNumber: int = 0


__all__ = ["TtsHandleFull"]
