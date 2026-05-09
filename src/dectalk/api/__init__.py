"""High-level DECtalk API."""

from dectalk.api.speak import UnknownWordError, speak, text_to_phonemes, to_wav

__all__ = ["UnknownWordError", "speak", "text_to_phonemes", "to_wav"]
