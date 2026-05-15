"""``NasalZero`` nasal anti-resonator placement from nasalf1x.c.

Translated from ``src/dapi/src/hlsyn/nasalf1x.c`` lines 131-188.

Computes the nasal-zero centre frequency ``FNZ`` (Hz) and the
nasal-zero bandwidth ``BNZ`` (Hz) from the current frame's nasal
area ``an`` (mm^2), the speaker's nasal-tract parameters, and the
constriction-modified first formant ``state.f1c`` (Hz). The result
parameterises the anti-resonator that cancels the nasal pole, so
the two move in tandem as the nasal area opens or closes.

The mathematics mirrors the Stevens / Williams nasal model:

- ``fn`` -- pure nasal-cavity formant (table lookup on ``an``,
  rescaled by ``speaker.fno / ANFN_TABLE_FNO``).
- ``fm`` -- movable formant tracking F2/F3 (see :func:`.compute_fm`).
- ``L/A`` -- effective nasal-mass per cross-section (table lookup
  on ``f1c``).
- ``MmOverMn = (L/A) * an / (3.7 * an + 100)`` -- the nasal-mass
  ratio that drives both the FNZ pull-down toward ``fm`` and the
  high-``f1c`` BNZ widening.

The square-root in ``FNZ`` goes through :func:`.dt_f_sqrt` (the
table-driven approximation the C binary uses) for bit-accurate
parity with ``libtts_us.so``.
"""

from __future__ import annotations

from dectalk.hlsyn.compute_fm import compute_fm
from dectalk.hlsyn.interpolate import interpolate_table
from dectalk.hlsyn.nasal_tables import (
    ANFN_TABLE,
    ANFN_TABLE_FNO,
    F1_LOVER_A_TABLE,
    NASAL_BANDWIDTH,
)
from dectalk.hlsyn.sqrt_table import dt_f_sqrt
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState


def nasal_zero(
    frame: HLFrame,
    speaker: HLSpeaker,
    state: HLState,
) -> tuple[float, float]:
    """Return the nasal-zero ``(FNZ, BNZ)`` in Hz.

    Faithful translation of:

    .. code-block:: c

        static void
        NasalZero(HLFrame *frame, HLSpeaker *speaker, HLState *state,
                  float *pFNZ, float *pBNZ)
        {
            float fn, fm, LOverA, MmOverMn,
                  an = MAX(0.0f, frame->an);

            fn = InterpolateTable(anfnTable, MAXANFN, an)
                 * (speaker->fno / anfnTable_fno);
            fm = Compute_fm(frame, speaker);
            LOverA = InterpolateTable(f1LOverATable, MAXF1LOVERA,
                                      state->f1c);
            MmOverMn = (float)(LOverA * an / (3.7f * an + 100.f));

            *pFNZ = fn * (float) DTsqrt((1.f + MmOverMn)
                  / (1.f + MmOverMn * fn * fn / (fm * fm)));

            if (state->f1c < speaker->BNZ_f1BreakPoint)
                *pBNZ = NasalBandwidth;
            else
                *pBNZ = NasalBandwidth + 100.0f * MmOverMn;
        }

    The C source's ``DEBUG`` branch (assertions on ``fn < FNZ < fm``)
    is silent in release builds and is not reproduced here.

    Args:
        frame: HL frame; reads ``an``.
        speaker: HL speaker definition; reads ``fno``,
            ``fm_f1BreakPoint`` (via :func:`compute_fm`), and
            ``BNZ_f1BreakPoint``.
        state: HL state; reads ``f1c``.

    Returns:
        ``(FNZ, BNZ)`` -- nasal-zero centre frequency and bandwidth
        in Hz. The bandwidth is at least :data:`.NASAL_BANDWIDTH`
        (200 Hz); the centre frequency lies between ``fn`` and ``fm``.
    """
    an = max(0.0, frame.an)

    # The an->fn table is calibrated at ANFN_TABLE_FNO=500 Hz; rescale
    # to the speaker's actual fno.
    fn = interpolate_table(ANFN_TABLE, an) * (speaker.fno / ANFN_TABLE_FNO)

    fm = compute_fm(frame, speaker)

    # Constriction-modified f1 drives the nasal-mass ratio.
    l_over_a = interpolate_table(F1_LOVER_A_TABLE, state.f1c)

    mm_over_mn = l_over_a * an / (3.7 * an + 100.0)

    fnz = fn * dt_f_sqrt((1.0 + mm_over_mn) / (1.0 + mm_over_mn * fn * fn / (fm * fm)))

    if state.f1c < speaker.BNZ_f1BreakPoint:
        bnz = NASAL_BANDWIDTH
    else:
        bnz = NASAL_BANDWIDTH + 100.0 * mm_over_mn

    return fnz, bnz


# Aliases under the original C-source names for inventory tests.
NasalZero = nasal_zero

__all__ = [
    "NasalZero",
    "nasal_zero",
]
