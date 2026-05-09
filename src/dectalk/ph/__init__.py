"""Phoneme features, intonation, durations, and frame sequencing.

Translated and adapted from `src/dapi/src/ph/`. Re-exports the
phoneme-string → audio entry point and the frame-target lookup.
"""

from dectalk.ph.phoneme_frames import get_frames
from dectalk.ph.sequencer import synthesize_phonemes

__all__ = ["get_frames", "synthesize_phonemes"]
