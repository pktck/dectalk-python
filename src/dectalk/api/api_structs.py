"""Public-facing API structs from ttsapi.h.

Translated from ``src/dapi/src/api/ttsapi.h``. These data structures
are the public types ``TextToSpeech*`` API functions take and return:

- :class:`LanguageParams` — single language descriptor (id + flags).
- :class:`TtsCaps` — engine capabilities (languages, sample rate,
  rate range, predefined speaker count).
- :class:`TtsPhoneme` — one phoneme change event delivered by the
  ``TTS_MSG_BUFFER`` callback.
- :class:`TtsIndex` — one index marker event.
- :class:`TtsBuffer` — speech-to-memory output buffer descriptor.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LanguageParams:
    """One language entry in :class:`TtsCaps.lp_language_params_array`.

    Faithful translation of:

    .. code-block:: c

        typedef struct LANGUAGE_PARAMS_TAG {
            LANGUAGE_T dwLanguage;       // language id (1=US, 2=UK, ...)
            DWORD dwLanguageAttributes;  // feature flags
        } LANGUAGE_PARAMS_T;

    Attributes:
        dw_language: Language ID.
        dw_language_attributes: Bitmask of feature flags.
    """

    dw_language: int = 0
    dw_language_attributes: int = 0


@dataclass(slots=True)
class TtsCaps:
    """Engine capability report (from ``TextToSpeechGetCaps``).

    Attributes:
        dw_number_of_languages: Languages supported.
        lp_language_params_array: List of :class:`LanguageParams`,
            one per supported language. (C source uses a pointer.)
        dw_sample_rate: Output sample rate in Hz.
        dw_minimum_speaking_rate: Lower bound of ``[:rate]``.
        dw_maximum_speaking_rate: Upper bound.
        dw_number_of_predefined_speakers: Voice count (9 for US).
        dw_character_set: Input character set ID.
        version: Engine version code.
    """

    dw_number_of_languages: int = 0
    lp_language_params_array: list[LanguageParams] = field(default_factory=list[LanguageParams])
    dw_sample_rate: int = 0
    dw_minimum_speaking_rate: int = 0
    dw_maximum_speaking_rate: int = 0
    dw_number_of_predefined_speakers: int = 0
    dw_character_set: int = 0
    version: int = 0


@dataclass(slots=True)
class TtsPhoneme:
    """One phoneme change event in the callback stream.

    Faithful translation of:

    .. code-block:: c

        typedef struct TTS_PHONEME_TAG {
            DWORD dwPhoneme;
            DWORD dwPhonemeSampleNumber;
            DWORD dwPhonemeDuration;
            DWORD dwReserved;
        } TTS_PHONEME_T;

    Attributes:
        dw_phoneme: 32-bit packed phoneme code (cThis + cNext bytes).
        dw_phoneme_sample_number: Sample index at which this phoneme
            starts in the output buffer.
        dw_phoneme_duration: Duration of the phoneme in samples.
        dw_reserved: Reserved field (zero).
    """

    dw_phoneme: int = 0
    dw_phoneme_sample_number: int = 0
    dw_phoneme_duration: int = 0
    dw_reserved: int = 0


@dataclass(slots=True)
class TtsIndex:
    """One index marker event in the callback stream.

    Faithful translation of:

    .. code-block:: c

        typedef struct TTS_INDEX_TAG {
            DWORD dwIndexValue;
            DWORD dwIndexSampleNumber;
            DWORD dwReserved;
        } TTS_INDEX_T;

    Attributes:
        dw_index_value: User-supplied index value.
        dw_index_sample_number: Sample index at which the index
            marker was hit.
        dw_reserved: Reserved field (zero).
    """

    dw_index_value: int = 0
    dw_index_sample_number: int = 0
    dw_reserved: int = 0


@dataclass(slots=True)
class TtsBuffer:
    """Speech-to-memory output buffer.

    Used by ``TextToSpeechAddBuffer`` / ``TextToSpeechReturnBuffer``.
    The Python port stores the audio data as :class:`bytearray` and
    the phoneme / index event lists as Python lists.

    Attributes:
        lp_data: PCM audio output (16-bit little-endian).
        lp_phoneme_array: Phoneme change events captured during
            synthesis.
        lp_index_array: Index marker events.
        dw_maximum_buffer_length: Capacity of ``lp_data`` in bytes.
        dw_maximum_number_of_phoneme_changes: Capacity of
            ``lp_phoneme_array``.
        dw_maximum_number_of_index_marks: Capacity of
            ``lp_index_array``.
        dw_buffer_length: Actual bytes filled in ``lp_data``.
        dw_number_of_phoneme_changes: Actual phoneme events written.
        dw_number_of_index_marks: Actual index events written.
        dw_reserved: Reserved field (zero).
    """

    lp_data: bytearray = field(default_factory=bytearray)
    lp_phoneme_array: list[TtsPhoneme] = field(default_factory=list[TtsPhoneme])
    lp_index_array: list[TtsIndex] = field(default_factory=list[TtsIndex])
    dw_maximum_buffer_length: int = 0
    dw_maximum_number_of_phoneme_changes: int = 0
    dw_maximum_number_of_index_marks: int = 0
    dw_buffer_length: int = 0
    dw_number_of_phoneme_changes: int = 0
    dw_number_of_index_marks: int = 0
    dw_reserved: int = 0


__all__ = [
    "LanguageParams",
    "TtsBuffer",
    "TtsCaps",
    "TtsIndex",
    "TtsPhoneme",
]
