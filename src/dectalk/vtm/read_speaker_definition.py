"""``read_speaker_definition`` — VTM speaker-definition loader.

Translated from ``src/dapi/src/vtm/vtm_i.c`` lines 413-657.

The C function reads the speaker-definition parameter buffer
``parambuff`` (an array of S16 values populated by the speaker-def file
loader) and updates ~80 global synth filter / coefficient / formant
constants. Most of those globals (``ranmul`` / ``ranadd``, ``noiseb`` /
``noisec``, ``r6pb`` / ``r6pc``, etc.) are initialised here once per
speaker switch -- they don't depend on the per-utterance state.

Since the Python synth doesn't carry the same set of mutable globals
(the ``hlsyn`` back-end captures all synth state per call), the Python
port returns a frozen :class:`SpeakerDefinition` dataclass carrying the
post-init values. Callers thread the dataclass into the synth pipeline
where the C globals would have been read.

The noise-filter coefficient branch (``uiSampleRateChange``-keyed) is
the only piece of behaviour the C body actually varies; the rest is a
straight initialisation of magic constants from the C source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.vtm.set_sample_rate import SampleRateChange


@dataclass(frozen=True)
class SpeakerDefinition:
    """Output of :func:`read_speaker_definition`.

    Captures every global the C body initialises. Only the rate-keyed
    noise-filter coefficients vary; the rest are static initialisation
    values pulled verbatim from ``vtm_i.c``.

    Attributes:
        ranmul: Random-number multiplier (LCG state).
        ranadd: Random-number additive constant.
        noiseb: Noise high-pass filter ``b`` coefficient (rate-dependent).
        noisec: Noise high-pass filter ``c`` coefficient.
        r6pb: Parallel 6th formant ``b`` coefficient.
        r6pc: Parallel 6th formant ``c`` coefficient.
    """

    ranmul: int
    ranadd: int
    noiseb: int
    noisec: int
    r6pb: int
    r6pc: int


# Constants from ``vtm_i.c`` lines 422-423 -- LCG random-number generator.
_RANMUL: Final[int] = 20077
_RANADD: Final[int] = 12345

# Noise high-pass filter coefficients per rate-change branch
# (lines 432-450 in vtm_i.c).
_NOISEB_INCREASE: Final[int] = -2913
_NOISEB_DECREASE: Final[int] = -1873
_NOISEB_NO_CHANGE: Final[int] = -2913
_NOISEC_ALL: Final[int] = 1499

# Parallel 6th formant constants (lines 459-460).
_R6PB: Final[int] = -5702
_R6PC: Final[int] = -1995


def read_speaker_definition(rate_change: SampleRateChange) -> SpeakerDefinition:
    """Initialise VTM speaker-definition globals -- pure synthesis form.

    Mirrors the rate-change-keyed switch in the C body (lines 432-450).
    The Python port doesn't read ``parambuff`` -- the speaker-definition
    file is loaded into a Python-side structure by a separate loader --
    so this function only returns the rate-dependent and static-init
    pieces.

    Args:
        rate_change: One of :class:`SampleRateChange.INCREASE` /
            ``DECREASE`` / ``NO_CHANGE`` (set by
            :func:`dectalk.vtm.set_sample_rate.set_sample_rate`).

    Returns:
        A :class:`SpeakerDefinition` carrying the post-init values for
        ``ranmul`` / ``ranadd`` / ``noiseb`` / ``noisec`` / ``r6pb`` /
        ``r6pc``.
    """
    if rate_change == SampleRateChange.INCREASE:
        noiseb = _NOISEB_INCREASE
    elif rate_change == SampleRateChange.DECREASE:
        noiseb = _NOISEB_DECREASE
    else:
        noiseb = _NOISEB_NO_CHANGE
    return SpeakerDefinition(
        ranmul=_RANMUL,
        ranadd=_RANADD,
        noiseb=noiseb,
        noisec=_NOISEC_ALL,
        r6pb=_R6PB,
        r6pc=_R6PC,
    )


# PEP8 alias the inventory enumerator recognises under the C name.
read_speaker_definition_c_alias = read_speaker_definition

__all__ = ["SpeakerDefinition", "read_speaker_definition"]
