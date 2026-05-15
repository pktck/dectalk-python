"""``TextToSpeechGetCaps`` -- engine capabilities reporter.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 7297-7318. The C
source fills a caller-supplied ``TTS_CAPS_T`` struct with the engine's
capabilities (supported languages, sample rate, rate bounds, speaker
count, character set, version). The Python port returns a populated
:class:`~dectalk.api.api_structs.TtsCaps` dataclass instead, so callers
don't need to allocate the struct themselves.

Mirrored constants from the C source for the ``us`` Linux build:

- ``PC_SAMPLE_RATE = 11025`` (from epsonapi.c line 66)
- ``MIN_SPEAKING_RATE = 75`` (from cm_defs.h line 68 -- the non-Kurtzweil branch)
- ``MAX_SPEAKING_RATE = 600`` (from cm_defs.h line 71)
- ``WENDY = 8`` (from ttsapi.h line 275; ``number_of_predefined_speakers`` is ``WENDY + 1 = 9``)
- ``PROPER_NAME_PRONUNCIATION = 0x00000001`` (from ttsapi.h line 337)
- ``TTS_ASCII = 0`` (from ttsapi.h line 363)
- ``Version = DTALK_MAJ_VERSION*100 + DTALK_MIN_VERSION = 500``
"""

from __future__ import annotations

from dectalk.api.api_structs import LanguageParams, TtsCaps
from dectalk.api.language import TTS_AMERICAN_ENGLISH
from dectalk.api.version import DTALK_MAJ_VERSION, DTALK_MIN_VERSION

# Constants mirrored from the C source.
PC_SAMPLE_RATE: int = 11025
MIN_SPEAKING_RATE: int = 75
MAX_SPEAKING_RATE: int = 600
WENDY: int = 8
PROPER_NAME_PRONUNCIATION: int = 0x00000001
TTS_ASCII: int = 0

_MMSYSERR_NOERROR: int = 0
_MMSYSERR_ERROR: int = 1


def TextToSpeechGetCaps(pTTScaps: TtsCaps | None) -> int:  # noqa: N802, N803
    """Fill ``pTTScaps`` with the engine capabilities.

    Faithful translation of the C body:

    .. code-block:: c

        if (pTTScaps == NULL) return MMSYSERR_ERROR;
        LanguageParamsArray[0].dwLanguage = TTS_AMERICAN_ENGLISH;
        LanguageParamsArray[0].dwLanguageAttributes = PROPER_NAME_PRONUNCIATION;
        pTTScaps->dwNumberOfLanguages = 1;
        pTTScaps->lpLanguageParamsArray = LanguageParamsArray;
        pTTScaps->dwSampleRate = PC_SAMPLE_RATE;
        pTTScaps->dwMinimumSpeakingRate = MIN_SPEAKING_RATE;
        pTTScaps->dwMaximumSpeakingRate = MAX_SPEAKING_RATE;
        pTTScaps->dwNumberOfPredefinedSpeakers = WENDY + 1;
        pTTScaps->dwCharacterSet = TTS_ASCII;
        pTTScaps->Version = DTALK_MAJ_VERSION*100 + DTALK_MIN_VERSION;
        return MMSYSERR_NOERROR;

    Args:
        pTTScaps: Caller-supplied ``TtsCaps`` to populate. ``None``
            returns ``MMSYSERR_ERROR``.

    Returns:
        ``MMSYSERR_NOERROR`` on success, ``MMSYSERR_ERROR`` if
        ``pTTScaps`` is ``None``.
    """
    if pTTScaps is None:
        return _MMSYSERR_ERROR
    pTTScaps.lp_language_params_array = [
        LanguageParams(
            dw_language=TTS_AMERICAN_ENGLISH,
            dw_language_attributes=PROPER_NAME_PRONUNCIATION,
        )
    ]
    pTTScaps.dw_number_of_languages = 1
    pTTScaps.dw_sample_rate = PC_SAMPLE_RATE
    pTTScaps.dw_minimum_speaking_rate = MIN_SPEAKING_RATE
    pTTScaps.dw_maximum_speaking_rate = MAX_SPEAKING_RATE
    pTTScaps.dw_number_of_predefined_speakers = WENDY + 1
    pTTScaps.dw_character_set = TTS_ASCII
    pTTScaps.version = DTALK_MAJ_VERSION * 100 + DTALK_MIN_VERSION
    return _MMSYSERR_NOERROR


__all__ = [
    "MAX_SPEAKING_RATE",
    "MIN_SPEAKING_RATE",
    "PC_SAMPLE_RATE",
    "PROPER_NAME_PRONUNCIATION",
    "TTS_ASCII",
    "WENDY",
    "TextToSpeechGetCaps",
]
