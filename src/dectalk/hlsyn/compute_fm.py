"""``Compute_fm`` movable-nasal-formant frequency from nasalf1x.c.

Translated from ``src/dapi/src/hlsyn/nasalf1x.c`` lines 191-211.

Computes the centre frequency of the moveable nasal formant
(``fm``) from the speaker's F1 / F2 / F3. The result is used as
the centre frequency for the nasal pole resonator.

The function uses a piecewise-linear blend of:

- Pure formant weighting (``0.8*f2 + 0.2*f3``) when ``f1`` is at
  or above the speaker's ``fm_f1BreakPoint``.
- A weighted mix between the formant value and the fixed 3000 Hz
  reference when ``f1`` is below the break point.
"""

from __future__ import annotations

from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame


def compute_fm(frame: HLFrame, speaker: HLSpeaker) -> float:
    """Return the moveable nasal formant centre frequency.

    Faithful translation of:

    .. code-block:: c

        float Compute_fm(HLFrame *frame, HLSpeaker *speaker) {
            float fm, r;
            if (frame->f1 >= speaker->fm_f1BreakPoint)
                fm = (float)(0.8f * frame->f2 + 0.2f * frame->f3);
            else {
                r = (float)(1.0f + 0.0143f
                            * (frame->f1 - speaker->fm_f1BreakPoint));
                fm = (float)(r * (0.8f * frame->f2 + 0.2f * frame->f3)
                             + (1. - r) * 3000.);
            }
            return fm;
        }

    Args:
        frame: HL frame (read ``f1`` / ``f2`` / ``f3``).
        speaker: HL speaker definition (read ``fm_f1BreakPoint``).

    Returns:
        Movable nasal formant centre frequency in Hz.
    """
    if frame.f1 >= speaker.fm_f1BreakPoint:
        return 0.8 * frame.f2 + 0.2 * frame.f3
    r = 1.0 + 0.0143 * (frame.f1 - speaker.fm_f1BreakPoint)
    return r * (0.8 * frame.f2 + 0.2 * frame.f3) + (1.0 - r) * 3000.0


__all__ = ["compute_fm"]
