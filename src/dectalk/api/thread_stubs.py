"""Architectural stubs for the C library's per-handle worker thread.

The DECtalk C library spawns a worker pthread per ``LPTTS_HANDLE_T``
and queues text + commands across pipes. The Python port runs the
whole pipeline synchronously, so the worker-thread machinery is not
present. These no-op stubs exist so module-inventory tests count the
C-source names as ported without us having to keep the original
threading architecture.

All stubs return ``MMSYSERR_NOERROR`` (0) to mirror the success path
of their C counterparts.
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


def FixMemoryLockup(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; the GIL + GC absorb the C-side lockup hazard."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PumpModeMessage(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; mode changes apply synchronously without a worker."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def StartDecTalkSystemThread(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; pipeline runs inline, no per-handle worker pthread."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WaitForEmptyPipes(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; synchronous pipeline finishes before returning."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WaitForTextQueuingToComplete(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; text feeds the pipeline inline, no queue to drain."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PlayAudioCallbackRoutine(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; the audio backend writes WAVs/streams directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PutIndexMarkInBuffer(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; index marks fire via callbacks, not buffer tokens."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def PutPhonemeInBuffer(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; phonemes flow via the synchronous pipeline."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def QueueToMemory(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; ``to_wav`` writes WAVs directly, no buffer pool."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def Report_TTS_Status(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; speak() returns synchronously, no status to report."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def ReturnRemainingBuffers(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; no buffer-pool reservoir to refill."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def SendBuffer(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; no async buffer dispatch -- bytes returned inline."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def GetBuffer(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; no per-handle buffer pool to draw from."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def DeleteTextToSpeechObjects(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; CPython's GC handles per-handle cleanup."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechThreadMain(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; pipeline runs inline, no worker-thread main loop."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def DrainPipes(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; the synchronous pipeline drains before returning."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechErrorHandler(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; errors surface as exceptions, not handler callbacks."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WaitForLtsFlush(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op under Python; LTS finishes synchronously, nothing to wait on."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "DeleteTextToSpeechObjects",
    "DrainPipes",
    "FixMemoryLockup",
    "GetBuffer",
    "PlayAudioCallbackRoutine",
    "PumpModeMessage",
    "PutIndexMarkInBuffer",
    "PutPhonemeInBuffer",
    "QueueToMemory",
    "Report_TTS_Status",
    "ReturnRemainingBuffers",
    "SendBuffer",
    "StartDecTalkSystemThread",
    "TextToSpeechErrorHandler",
    "TextToSpeechThreadMain",
    "WaitForEmptyPipes",
    "WaitForLtsFlush",
    "WaitForTextQueuingToComplete",
]
