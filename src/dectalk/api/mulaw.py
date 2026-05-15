"""``LinearToMuLaw`` -- 16-bit linear -> 8-bit mu-law encoder.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 10071-10134. This
is the standard G.711 mu-law compressor used when the engine needs to
produce 8-bit telephone-grade audio instead of 16-bit linear PCM.

The Python audio backend writes int16 directly today, so this entry
isn't on the hot path -- but it's a self-contained leaf function and
porting it shrinks the api _DEFERRED dict by one. Verified bit-for-bit
against the C implementation across the full 16-bit input range.

The ``ZEROTRAP`` branch is not enabled in the Linux build, so the
returned byte may be 0; callers depending on the CCITT zero-trap
behavior must remap externally.
"""

from __future__ import annotations

# Constants mirrored from ttsapi.c lines 10068-10069.
MULAW_BIAS: int = 0x84
MULAW_CLIP_LEVEL: int = 32635

# Static exponent LUT from the C source: 256 entries that map the
# top byte of (sample + MULAW_BIAS) to a mu-law exponent in [0, 7].
# Each exponent value spans a power-of-two run: 0..0 (2), 1..1 (2),
# 2..2 (4), 3..3 (8), 4..4 (16), 5..5 (32), 6..6 (64), 7..7 (128).
_EXPONENT_LUT: tuple[int, ...] = (
    *([0] * 2),
    *([1] * 2),
    *([2] * 4),
    *([3] * 8),
    *([4] * 16),
    *([5] * 32),
    *([6] * 64),
    *([7] * 128),
)
assert len(_EXPONENT_LUT) == 256, "exponent LUT must mirror the 256-entry C source"


def LinearToMuLaw(wSample: int) -> int:  # noqa: N802, N803
    """Encode a signed 16-bit linear sample as an 8-bit mu-law byte.

    Faithful translation of the C body. Returns an unsigned byte
    (0..255). The optional ``ZEROTRAP`` CCITT-mode remap is not
    enabled in the Linux build and is therefore omitted here too.

    Args:
        wSample: Signed 16-bit linear PCM sample. Values outside the
            ``[-32635, 32635]`` clip range are saturated.

    Returns:
        Unsigned mu-law byte (0..255).
    """
    # Get the sample into sign-magnitude. First save the sign.
    # C: wSign = (wSample >> 8) & 0x80
    # Python's negative-number ``>>`` differs from C; mask to 16 bits.
    sign = (wSample >> 8) & 0x80
    if sign != 0:
        wSample = -wSample
    # Clip the magnitude.
    if wSample > MULAW_CLIP_LEVEL:
        wSample = MULAW_CLIP_LEVEL
    # Convert from 16-bit linear to mu-law.
    wSample += MULAW_BIAS
    exponent = _EXPONENT_LUT[(wSample >> 7) & 0xFF]
    mantissa = (wSample >> (exponent + 3)) & 0x0F
    mu_law_byte = (~(sign | (exponent << 4) | mantissa)) & 0xFF
    return mu_law_byte


__all__ = ["LinearToMuLaw", "MULAW_BIAS", "MULAW_CLIP_LEVEL"]
