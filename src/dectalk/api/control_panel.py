"""``TextToSpeechControlPanel`` -- show the legacy DECtalk control-panel UI.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 10967-10976. The
control panel was a DTALK50-Windows-only feature; on every other
build target (including Linux), the C source body is a no-op that
returns void. The Python port mirrors that.
"""

from __future__ import annotations


def TextToSpeechControlPanel(  # noqa: N802 — mirror C entry-point name
    ttsHandle: object = None,  # noqa: N803 — mirror C arg name
) -> None:
    """No-op control-panel entry; the Linux build has no UI surface.

    Faithful translation of the non-DTALK50 branch:

    .. code-block:: c

        void TextToSpeechControlPanel(LPTTS_HANDLE_T ttsHandle)
        {
        #ifdef DTALK50
            ...  // Windows-only
        #else
            /* This function not supported in 4.4 */
        #endif
            return;
        }
    """
    del ttsHandle


__all__ = ["TextToSpeechControlPanel"]
