"""Cross-platform Python port of DECtalk text-to-speech.

Public API:

- :func:`speak` — text → ``int16`` PCM samples.
- :func:`to_wav` — text → WAV file.
- :func:`play` — play PCM samples through the default audio device.
- :func:`write_wav` — write PCM samples to a WAV file.
- :func:`synthesize_phonemes` — ARPABET phoneme list → PCM.
- :exc:`UnknownWordError` — raised when a word is missing from the
  bundled lexicon.

Example:
    >>> import dectalk
    >>> samples = dectalk.speak("hello world")
    >>> dectalk.write_wav(samples, "hello.wav")
"""

from dectalk.api import (
    UnknownWordError,
    speak,
    text_to_dectalk_phonemes,
    text_to_phonemes,
    to_wav,
)
from dectalk.nt.audio import play, sine_tone, write_wav
from dectalk.ph.sequencer import synthesize_phonemes

__all__ = [
    "UnknownWordError",
    "play",
    "sine_tone",
    "speak",
    "synthesize_phonemes",
    "text_to_dectalk_phonemes",
    "text_to_phonemes",
    "to_wav",
    "write_wav",
]
__version__ = "0.1.0"
