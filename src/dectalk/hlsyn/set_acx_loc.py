"""``Set_acx_loc`` constriction-location selector from acxf1c.c.

Translated from ``src/dapi/src/hlsyn/acxf1c.c`` lines 241-310.

Picks the smallest constriction area across the four candidate
loci (lips / blade / dorsum / liquid) and writes the result to
``state.acx`` and the dominant-location code to ``state.loc``.
Ties are broken by preferring the location furthest from the
lips (back > front), matching the C source's nested ``<=``
comparisons.
"""

from __future__ import annotations

from dectalk.hlsyn.place_constants import BLADE, DORSUM, LIPS, LIQUID, UNCOMPUTABLE
from dectalk.ph.hlsyn_structs import HLFrame, HLState


def set_acx_loc(frame: HLFrame, state: HLState) -> None:
    """Select the dominant constriction and write to ``state.acx`` / ``state.loc``.

    Faithful translation of:

    .. code-block:: c

        void Set_acx_loc(HLFrame *frame, HLState *state) {
            float LiquidDorsumArea, LipsBladeArea;
            short LiquidDorsumPlace, LipsBladePlace;

            // Liquid vs Dorsum -> back constriction.
            if (state->acl == UNCOMPUTABLE) {
                LiquidDorsumArea = state->acd;
                LiquidDorsumPlace = DORSUM;
            } else if (state->acd <= state->acl) {
                LiquidDorsumArea = state->acd;
                LiquidDorsumPlace = DORSUM;
            } else {
                LiquidDorsumArea = state->acl;
                LiquidDorsumPlace = LIQUID;
            }

            // Lips vs Blade -> front constriction.
            if (frame->ab <= frame->al) {
                LipsBladeArea = frame->ab;
                LipsBladePlace = BLADE;
            } else {
                LipsBladeArea = frame->al;
                LipsBladePlace = LIPS;
            }

            // Smaller of the two wins; ties go to the back.
            if (LiquidDorsumArea <= LipsBladeArea) {
                state->acx = LiquidDorsumArea;
                state->loc = LiquidDorsumPlace;
            } else {
                state->acx = LipsBladeArea;
                state->loc = LipsBladePlace;
            }
        }

    Args:
        frame: HL frame (read ``ab`` and ``al`` for the front
            constrictions).
        state: HL state (read ``acl`` / ``acd`` for the back
            constrictions; write ``acx`` / ``loc``).
    """
    # Liquid vs Dorsum -> back constriction.
    if state.acl == UNCOMPUTABLE or state.acd <= state.acl:
        liquid_dorsum_area = state.acd
        liquid_dorsum_place = DORSUM
    else:
        liquid_dorsum_area = state.acl
        liquid_dorsum_place = LIQUID

    # Lips vs Blade -> front constriction.
    if frame.ab <= frame.al:
        lips_blade_area = frame.ab
        lips_blade_place = BLADE
    else:
        lips_blade_area = frame.al
        lips_blade_place = LIPS

    # Smaller of the two wins; ties go to the back.
    if liquid_dorsum_area <= lips_blade_area:
        state.acx = liquid_dorsum_area
        state.loc = liquid_dorsum_place
    else:
        state.acx = lips_blade_area
        state.loc = lips_blade_place


__all__ = ["set_acx_loc"]
