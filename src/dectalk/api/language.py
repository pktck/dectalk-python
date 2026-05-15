"""Public API language get/set functions.

Translated from ``src/dapi/src/api/ttsapi.c``:

- :func:`TextToSpeechGetLanguage` (lines 7196-7209) -- always
  returns ``TTS_AMERICAN_ENGLISH`` for any valid handle.
- :func:`TextToSpeechSetLanguage` (lines 7246-7260) -- accepts only
  ``TTS_AMERICAN_ENGLISH``, returns ``MMSYSERR_INVALPARAM`` otherwise.

The Python runtime only ships US English today, so both functions
mirror the C source's narrow language-validation behavior.
"""

from __future__ import annotations

# Language ID constants from ``src/dapi/src/api/ttsapi.h`` (the
# ``LANGUAGE_T`` enum). Only the one we use is exposed.
TTS_AMERICAN_ENGLISH: int = 0x0409  # MAKELANGID(LANG_ENGLISH, SUBLANG_ENGLISH_US)

# MMSYSERR codes (mirrored from Windows multimedia constants used by the C API).
_MMSYSERR_NOERROR: int = 0
_MMSYSERR_INVALHANDLE: int = 5
_MMSYSERR_INVALPARAM: int = 11


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


def TextToSpeechSetLanguage(  # noqa: N802 — mirror C entry-point name
    phTTS: object,  # noqa: N803 — mirror C argument name
    Language: int,  # noqa: N803 — mirror C argument name
) -> int:
    """Set the language on ``phTTS``; only ``TTS_AMERICAN_ENGLISH`` accepted.

    Faithful translation of the C body:

    .. code-block:: c

        if ( IsBadWritePtr( phTTS, sizeof(phTTS)))
            return( MMSYSERR_INVALHANDLE );
        if ( Language != TTS_AMERICAN_ENGLISH )
            return( MMSYSERR_INVALPARAM );
        return( MMSYSERR_NOERROR );

    Args:
        phTTS: TTS handle. ``None`` returns ``MMSYSERR_INVALHANDLE``.
        Language: Language ID; must be ``TTS_AMERICAN_ENGLISH``.

    Returns:
        ``MMSYSERR_NOERROR`` on success, ``MMSYSERR_INVALHANDLE`` for a
        ``None`` handle, ``MMSYSERR_INVALPARAM`` for any non-US-English
        language.
    """
    if phTTS is None:
        return _MMSYSERR_INVALHANDLE
    if Language != TTS_AMERICAN_ENGLISH:
        return _MMSYSERR_INVALPARAM
    return _MMSYSERR_NOERROR


__all__ = [
    "TTS_AMERICAN_ENGLISH",
    "TextToSpeechGetLanguage",
    "TextToSpeechSetLanguage",
]
