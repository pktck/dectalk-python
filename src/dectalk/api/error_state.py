"""``TextToSpeechGetLastError`` -- public last-error accessor.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 10982-10986. The C
source body is a one-liner:

.. code-block:: c

    unsigned int TextToSpeechGetLastError(LPTTS_HANDLE_T phTTS)
    {
        return phTTS->LastError;
    }

The Python port mirrors that as a trivial accessor over any object
exposing a ``LastError`` integer attribute (``_capi.CAPI`` handles
or test stubs).
"""

from __future__ import annotations

from typing import Protocol


class _HasLastError(Protocol):
    """Protocol for any TTS-handle-like object exposing a ``LastError`` slot."""

    LastError: int


def TextToSpeechGetLastError(phTTS: _HasLastError) -> int:  # noqa: N802, N803
    """Return ``phTTS.LastError`` -- the handle's most recent MMRESULT.

    Faithful one-line translation. The caller is responsible for
    ensuring ``phTTS`` exposes the ``LastError`` integer slot; the C
    source does no NULL check on the pointer, and neither do we.
    """
    return phTTS.LastError


__all__ = ["TextToSpeechGetLastError"]
