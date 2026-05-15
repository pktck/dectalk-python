"""``MapGlottalFormantsNotF1`` HL-to-LL formant copy with tracheal-coupling f1c bump.

Translated from ``src/dapi/src/hlsyn/hlframe.c`` lines 181-225
(``MapGlottalFormantsNotF1``). This is one of the private helpers
``HLSynthesizeLLFrame`` calls after ``Tongue_acx_f1c`` /
``SpeechCircuit``. It does three things:

1. Copies ``frame.f0`` into ``llframe.NF0`` (rounded, clamped to >= 0;
   the helper writes 0 when ``frame.f0`` is non-positive).
2. Adjusts the constriction-adjusted first formant ``state.f1c`` for
   tracheal coupling. When the nasal area is small (``an < 3``) and
   ``f1c`` is in the low-F1 range (``< 185 Hz``) and the glottal flow
   area exceeds the modal threshold (``agf > agm``), F1 is dragged
   toward the tracheal pole ``F1T`` by an amount proportional to
   ``KdF * (1 - f1c/F1T) * (agf - agm)``.
3. Copies ``frame.f2`` / ``frame.f3`` / ``frame.f4`` and the
   speaker-wide ``F5`` into ``llframe.NF2`` / ``.NF3`` / ``.NF4`` /
   ``.NF5`` (each truncated toward zero by C's ``(short)`` cast).

There is an ``#ifdef in_phdraw`` block adding three correction terms
to ``NF0`` (vowel-height shift, transglottal-pressure correction, and
glottal-stiffness correction via ``Kf1`` / ``Kpd`` / ``Kdf0dc``). That
symbol is NOT defined in the Linux build, so the simpler body above is
what the C oracle actually runs.

Notes on the ``(short)`` cast:

- For positive floats, ``(short)x`` truncates toward zero, matching
  Python's ``int(x)``.
- For ``frame.f0``, the C source explicitly adds ``0.5f`` before the
  cast for round-half-to-even behaviour; we follow suit, then clamp at
  zero in the same arm of the conditional.
"""

from __future__ import annotations

from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState


def map_glottal_formants_not_f1(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
    llframe: LLFrameN,
) -> None:
    """Copy ``frame.f0/f2/f3/f4`` + ``speaker.F5`` to ``llframe`` (with f1c bump).

    Mirrors the Linux-active body of ``MapGlottalFormantsNotF1`` in
    ``hlframe.c``:

    .. code-block:: c

        if (frame->f0 > 0.0f) {
            llframe->NF0 = (short)(frame->f0 + 0.5f);
            if (llframe->NF0 < 0) llframe->NF0 = 0;
        } else {
            llframe->NF0 = 0;
        }

        if (frame->an < 3.0f && state->f1c < 185.0f)
            if (state->agf > speaker->agm && state->f1c < speaker->F1T)
                state->f1c += speaker->KdF * (1.0f - state->f1c / speaker->F1T)
                            * (state->agf - speaker->agm);

        llframe->NF2 = (short)frame->f2;
        llframe->NF3 = (short)frame->f3;
        llframe->NF4 = (short)frame->f4;
        llframe->NF5 = (short)speaker->F5;

    Args:
        frame: HL frame (read ``f0`` / ``f2`` / ``f3`` / ``f4`` and ``an``).
        speaker: HL speaker (read ``agm`` / ``F1T`` / ``KdF`` / ``F5``).
        state: HL state, mutated: ``f1c`` may be increased by the
            tracheal-coupling adjustment.
        llframe: LL frame, mutated: ``NF0`` / ``NF2`` / ``NF3`` / ``NF4`` /
            ``NF5`` are written.
    """
    if frame.f0 > 0.0:
        # Round, not truncate. The +0.5 then (short) cast matches the C.
        # The clamp at zero only matters when frame.f0 + 0.5 has truncated
        # to a negative integer, which the > 0 guard makes essentially
        # impossible -- but we mirror the C exactly.
        nf0 = int(frame.f0 + 0.5)
        llframe.NF0 = max(nf0, 0)
    else:
        llframe.NF0 = 0

    # Adjust f1c for tracheal coupling. Only applied when:
    # - the nasal area is small (an < 3): otherwise nasal coupling
    #   dominates and this regime is uncharted in the literature; and
    # - f1c is in the low-F1 regime (< 185 Hz): at high f1 the analysis
    #   hasn't been done and breathiness (chink) probably introduces a
    #   compensating compromise; and
    # - the glottal flow area exceeds the modal threshold (agf > agm); and
    # - f1c is below the tracheal pole F1T.
    if (
        frame.an < 3.0  # noqa: PLR2004 - nasal-area threshold from C source
        and state.f1c < 185.0  # noqa: PLR2004 - low-F1 threshold from C source
        and state.agf > speaker.agm
        and state.f1c < speaker.F1T
    ):
        state.f1c += speaker.KdF * (1.0 - state.f1c / speaker.F1T) * (state.agf - speaker.agm)

    # C's (short) cast truncates toward zero; int() in Python does the same.
    llframe.NF2 = int(frame.f2)
    llframe.NF3 = int(frame.f3)
    llframe.NF4 = int(frame.f4)
    llframe.NF5 = int(speaker.F5)


MapGlottalFormantsNotF1 = map_glottal_formants_not_f1

__all__ = ["MapGlottalFormantsNotF1", "map_glottal_formants_not_f1"]
