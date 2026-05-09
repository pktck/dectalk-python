"""Cross-platform Python port of DECtalk text-to-speech.

This is the public package entry point. Phase 0 of the port only exposes
the audio I/O primitives needed for smoke testing; the synthesizer, voice
selection, and language pipelines arrive in later phases.

Example:
    >>> from dectalk.nt import sine_tone, write_wav
    >>> tone = sine_tone(440.0, 0.5)
    >>> write_wav(tone, "/tmp/a440.wav")
"""

from dectalk.nt import play, write_wav
from dectalk.nt.audio import sine_tone

__all__ = ["play", "sine_tone", "write_wav"]
__version__ = "0.1.0"
