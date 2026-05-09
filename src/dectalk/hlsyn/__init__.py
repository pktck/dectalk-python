"""Klatt cascade-parallel formant synthesizer.

Translated from `src/dapi/src/hlsyn/`. Re-exports the public Klatt API:

- :class:`LLSynth`, :class:`LLFrame`, :class:`Speaker` — synthesizer types.
- :func:`ll_synthesize` — top-level frame synthesis function.
- :func:`next_sample`, :func:`next_voice_sample` — per-sample primitives.
"""

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.sample import next_sample
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.voice import (
    SOURCE_IMPULSIVE,
    SOURCE_LF,
    SOURCE_NATURAL,
    next_voice_sample,
)

__all__ = [
    "SOURCE_IMPULSIVE",
    "SOURCE_LF",
    "SOURCE_NATURAL",
    "LLFrame",
    "LLSynth",
    "Speaker",
    "ll_synthesize",
    "next_sample",
    "next_voice_sample",
]
