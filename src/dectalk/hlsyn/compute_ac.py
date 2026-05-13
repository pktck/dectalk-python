"""``Compute_acl`` / ``Compute_acd`` constriction-area helpers from acxf1c.c.

Translated from ``src/dapi/src/hlsyn/acxf1c.c`` lines 167-239.

These two helpers feed :func:`~dectalk.hlsyn.set_acx_loc.set_acx_loc`
with the two back-of-the-mouth constriction areas:

- :func:`compute_acl` -- *lateral / palato-alveolar* constriction area.
  Defined only when the frame's ``(f1, f2, f3)`` lands in the
  speaker's liquid (retroflex or lateral) range; otherwise returns
  :data:`~dectalk.hlsyn.place_constants.UNCOMPUTABLE`.
- :func:`compute_acd` -- *dorsal* constriction area. A
  Helmholtz-resonator inverse below the speaker's ``acd_f1Break``
  break frequency, switching to a higher-frequency quadratic
  fall-off above. Clamps to ``[0, speaker.acdMax]``.

The C source's ``CMSQ_TO_MMSQ`` macro multiplies by 100 (``cm^2`` to
``mm^2``); inlined here as a literal.
"""

from __future__ import annotations

from dectalk.hlsyn.helmholtz import helmholtz_constriction
from dectalk.hlsyn.place_constants import UNCOMPUTABLE
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame


def compute_acl(frame: HLFrame, speaker: HLSpeaker) -> float:
    """Return the lateral / palato-alveolar constriction area ``acl``.

    Faithful translation of:

    .. code-block:: c

        float Compute_acl(HLFrame *frame, HLSpeaker *speaker) {
            if ((speaker->f1Min < frame->f1 && frame->f1 < speaker->f1Max)
                && (   (frame->f2 < speaker->f2RetroflexMax
                     && frame->f3 < speaker->f3RetroflexMax)
                    || (frame->f2 < speaker->f2LateralMax
                     && frame->f3 > speaker->f3LateralMin)))
                return ((frame->f1 / speaker->aclFreq)
                      * (frame->f1 / speaker->aclFreq) * speaker->Kacl);
            else
                return UNCOMPUTABLE;
        }

    The liquid range is a band on ``f1`` (between ``f1Min`` and
    ``f1Max``) intersected with EITHER a retroflex region (low ``f2``
    AND low ``f3``) OR a lateral region (low ``f2`` AND high ``f3``).
    When the frame is in range, the area is a simple quadratic in
    ``f1`` normalised by ``aclFreq``.

    Args:
        frame: HL frame (read ``f1`` / ``f2`` / ``f3``).
        speaker: HL speaker (read ``f1Min`` / ``f1Max`` /
            ``f2RetroflexMax`` / ``f3RetroflexMax`` / ``f2LateralMax`` /
            ``f3LateralMin`` / ``aclFreq`` / ``Kacl``).

    Returns:
        ``(f1 / aclFreq) ** 2 * Kacl`` when the frame is in the liquid
        range, else :data:`UNCOMPUTABLE`.
    """
    if (speaker.f1Min < frame.f1 < speaker.f1Max) and (
        (frame.f2 < speaker.f2RetroflexMax and frame.f3 < speaker.f3RetroflexMax)
        or (frame.f2 < speaker.f2LateralMax and frame.f3 > speaker.f3LateralMin)
    ):
        # Cannot be negative if all values are positive.
        ratio = frame.f1 / speaker.aclFreq
        return ratio * ratio * speaker.Kacl
    return UNCOMPUTABLE


def compute_acd(frame: HLFrame, speaker: HLSpeaker) -> float:
    """Return the dorsal constriction area ``acd`` clamped to ``[0, acdMax]``.

    Faithful translation of:

    .. code-block:: c

        float Compute_acd(HLFrame *frame, HLSpeaker *speaker) {
            float acd, temp;
            if (frame->f1 < speaker->acd_f1Break) {
                acd = HelmholtzConstriction(frame->f1, speaker->Vacd,
                    speaker->Lc_acd, speaker->HelmholtzZeroAreaFrequency);
                acd = CMSQ_TO_MMSQ(acd);   // *100
            } else {
                temp = (speaker->f1HiShift - frame->f1)
                    / speaker->HelmholtzZeroAreaFrequency;
                acd = speaker->KHi * temp * temp - speaker->KHi;
            }
            if (acd > speaker->acdMax) return speaker->acdMax;
            else if (acd < 0.0f) return 0.f;
            else return acd;
        }

    Below ``acd_f1Break`` the area is the Helmholtz-resonator inverse
    of ``f1`` (CGS units, converted to ``mm^2``). Above the break,
    a higher-frequency quadratic fall-off in ``(f1HiShift - f1)``
    takes over. The result is clamped to ``[0, acdMax]``.

    The ``TONGUE_BODY_AREA_stillvalid_`` branch is selected by
    ``#ifndef``; since that symbol is not in the Linux build's
    defines, the first (break-frequency) branch is the active one.

    Args:
        frame: HL frame (read ``f1``).
        speaker: HL speaker (read ``Vacd`` / ``Lc_acd`` /
            ``HelmholtzZeroAreaFrequency`` / ``acd_f1Break`` /
            ``f1HiShift`` / ``KHi`` / ``acdMax``).

    Returns:
        Dorsal constriction area in ``mm^2``, clamped to
        ``[0, speaker.acdMax]``.
    """
    if frame.f1 < speaker.acd_f1Break:
        acd_cgs = helmholtz_constriction(
            frame.f1,
            speaker.Vacd,
            speaker.Lc_acd,
            speaker.HelmholtzZeroAreaFrequency,
        )
        # CMSQ_TO_MMSQ(acd): *100
        acd = acd_cgs * 100.0
    else:
        temp = (speaker.f1HiShift - frame.f1) / speaker.HelmholtzZeroAreaFrequency
        acd = speaker.KHi * temp * temp - speaker.KHi

    if acd > speaker.acdMax:
        return speaker.acdMax
    if acd < 0.0:
        return 0.0
    return acd


__all__ = ["compute_acd", "compute_acl"]
