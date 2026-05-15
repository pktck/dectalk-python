"""Bit-parity tests for :func:`dectalk.api.caps.TextToSpeechGetCaps`."""

from __future__ import annotations

from dectalk.api.api_structs import TtsCaps
from dectalk.api.caps import (
    MAX_SPEAKING_RATE,
    MIN_SPEAKING_RATE,
    PC_SAMPLE_RATE,
    PROPER_NAME_PRONUNCIATION,
    TTS_ASCII,
    TextToSpeechGetCaps,
    WENDY,
)
from dectalk.api.language import TTS_AMERICAN_ENGLISH


def test_null_argument_returns_error() -> None:
    """``pTTScaps == NULL`` -> ``MMSYSERR_ERROR (1)`` in the C source."""
    assert TextToSpeechGetCaps(None) == 1


def test_populates_caps_dataclass() -> None:
    """All slots get the C-faithful values for the ``us`` Linux build."""
    caps = TtsCaps()
    rc = TextToSpeechGetCaps(caps)
    assert rc == 0  # MMSYSERR_NOERROR
    assert caps.dw_number_of_languages == 1
    assert len(caps.lp_language_params_array) == 1
    lp = caps.lp_language_params_array[0]
    assert lp.dw_language == TTS_AMERICAN_ENGLISH
    assert lp.dw_language_attributes == PROPER_NAME_PRONUNCIATION
    assert caps.dw_sample_rate == PC_SAMPLE_RATE
    assert caps.dw_minimum_speaking_rate == MIN_SPEAKING_RATE
    assert caps.dw_maximum_speaking_rate == MAX_SPEAKING_RATE
    assert caps.dw_number_of_predefined_speakers == WENDY + 1
    assert caps.dw_character_set == TTS_ASCII
    # Version = DTALK_MAJ_VERSION*100 + DTALK_MIN_VERSION = 5*100 + 0 = 500
    assert caps.version == 500  # noqa: PLR2004


def test_constants_match_c_source() -> None:
    """Sanity check the mirrored values match coop.h / cm_defs.h / ttsapi.h."""
    assert PC_SAMPLE_RATE == 11025  # noqa: PLR2004
    assert MIN_SPEAKING_RATE == 75  # noqa: PLR2004
    assert MAX_SPEAKING_RATE == 600  # noqa: PLR2004
    assert WENDY == 8  # noqa: PLR2004
    assert PROPER_NAME_PRONUNCIATION == 0x00000001
    assert TTS_ASCII == 0
