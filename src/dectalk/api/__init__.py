"""High-level DECtalk API."""

from dectalk.api.speak import (
    UnknownWordError,
    available_voices,
    speak,
    text_to_phonemes,
    to_wav,
)

__all__ = [
    "UnknownWordError",
    "available_voices",
    "speak",
    "text_to_phonemes",
    "to_wav",
]
