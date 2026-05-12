"""Verify the public API struct dataclasses."""

from __future__ import annotations

from dectalk.api.api_structs import (
    LanguageParams,
    TtsBuffer,
    TtsCaps,
    TtsIndex,
    TtsPhoneme,
)


def test_language_params_defaults() -> None:
    """LanguageParams defaults to (0, 0)."""
    lp = LanguageParams()
    assert lp.dw_language == 0
    assert lp.dw_language_attributes == 0


def test_tts_caps_defaults() -> None:
    """TtsCaps defaults to all-zero fields and empty language list."""
    caps = TtsCaps()
    assert caps.dw_number_of_languages == 0
    assert caps.lp_language_params_array == []
    assert caps.dw_sample_rate == 0


def test_tts_caps_with_us_voice() -> None:
    """A representative US-voice capability report can be built."""
    caps = TtsCaps(
        dw_number_of_languages=1,
        lp_language_params_array=[LanguageParams(dw_language=1)],
        dw_sample_rate=11025,
        dw_minimum_speaking_rate=75,
        dw_maximum_speaking_rate=600,
        dw_number_of_predefined_speakers=9,
    )
    assert caps.dw_number_of_languages == 1
    assert caps.dw_sample_rate == 11025
    assert caps.dw_number_of_predefined_speakers == 9
    assert caps.lp_language_params_array[0].dw_language == 1


def test_tts_phoneme_defaults() -> None:
    """TtsPhoneme defaults are all zero."""
    ph = TtsPhoneme()
    assert ph.dw_phoneme == 0
    assert ph.dw_phoneme_sample_number == 0
    assert ph.dw_phoneme_duration == 0
    assert ph.dw_reserved == 0


def test_tts_index_defaults() -> None:
    """TtsIndex defaults are all zero."""
    ix = TtsIndex()
    assert ix.dw_index_value == 0
    assert ix.dw_index_sample_number == 0


def test_tts_buffer_defaults() -> None:
    """TtsBuffer defaults to empty data/lists."""
    buf = TtsBuffer()
    assert buf.lp_data == bytearray()
    assert buf.lp_phoneme_array == []
    assert buf.lp_index_array == []
    assert buf.dw_buffer_length == 0


def test_tts_buffer_with_payload() -> None:
    """A buffer can be filled with sample data and event lists."""
    buf = TtsBuffer(
        lp_data=bytearray(b"\x00\x01\x02\x03"),
        lp_phoneme_array=[TtsPhoneme(dw_phoneme=42)],
        lp_index_array=[TtsIndex(dw_index_value=7)],
        dw_buffer_length=4,
        dw_number_of_phoneme_changes=1,
        dw_number_of_index_marks=1,
    )
    assert buf.dw_buffer_length == 4
    assert buf.dw_number_of_phoneme_changes == 1
    assert buf.lp_phoneme_array[0].dw_phoneme == 42
    assert buf.lp_index_array[0].dw_index_value == 7


def test_dataclasses_use_slots() -> None:
    """All five dataclasses use slots=True."""
    for cls in (LanguageParams, TtsCaps, TtsPhoneme, TtsIndex, TtsBuffer):
        instance = cls()
        assert not hasattr(instance, "__dict__"), f"{cls.__name__} missing slots"
