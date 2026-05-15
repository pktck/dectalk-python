"""``TextToSpeechGetLanguage`` -- public API language-readback function.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 7196-7209. The C
source returns ``TTS_AMERICAN_ENGLISH`` (the language ID for US English)
for any valid handle. Python's port hard-codes the same since the
runtime only supports US English today.
"""

from __future__ import annotations

# Language ID constants from ``src/dapi/src/api/ttsapi.h`` (the
# ``LANGUAGE_T`` enum). Only the one we use is exposed.
TTS_AMERICAN_ENGLISH: int = 0x0409  # MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US)

# MMSYSERR codes (mirrored from Windows multimedia constants used by the C API).
_MMSYSERR_NOERROR: int = 0
_MMSYSERR_INVALHANDLE: int = 5


def TextToSpeechGetLanguage(  # noqa: N802 — mirror C entry-point name
    phTTS: object,  # noqa: N803 — mirror C argument name
    p_language: list[int] | None = None,
) -> int:
    """Read the active language for ``phTTS`` (US English in this port).

    Faithful translation of the C body:

    .. code-block:: c

        if ( IsBadWritePtr( phTTS, sizeof(phTTS)))
            return( MMSYSERR_INVALHANDLE );
        *pLanguage = TTS_AMERICAN_ENGLISH;
        return( MMSYSERR_NOERROR );

    Args:
        phTTS: TTS handle. ``None`` returns ``MMSYSERR_INVALHANDLE``.
        p_language: Single-element list used as an out-parameter; the
            language ID is written to ``p_language[0]`` when non-None.

    Returns:
        ``MMSYSERR_NOERROR`` (0) on success, ``MMSYSERR_INVALHANDLE``
        (5) when the handle is ``None``.
    """
    if phTTS is None:
        return _MMSYSERR_INVALHANDLE
    if p_language is not None:
        if p_language:
            p_language[0] = TTS_AMERICAN_ENGLISH
        else:
            p_language.append(TTS_AMERICAN_ENGLISH)
    return _MMSYSERR_NOERROR


__all__ = ["TTS_AMERICAN_ENGLISH", "TextToSpeechGetLanguage"]
