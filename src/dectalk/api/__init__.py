"""High-level DECtalk API."""

from dectalk.api.sing import sing, sing_to_wav
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
    "sing",
    "sing_to_wav",
    "speak",
    "text_to_phonemes",
    "to_wav",
]
