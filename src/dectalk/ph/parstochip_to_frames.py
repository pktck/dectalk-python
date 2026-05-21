"""Adapter from ``DphT.parstochip[]`` to :class:`LLFrame`.

The PH stage writes its per-frame Klatt parameters into the integer
array ``DphT.parstochip[]`` (one cell per ``OUT_*`` index). The
hlsyn back-end consumes :class:`~dectalk.hlsyn.llsyn.LLFrame` objects
instead. This module bridges the two formats one frame at a time.

The C driver (``ph_claus.c`` line 498's ``send_pars()``) eventually
delivers the same values to the synthesizer — but takes a more
elaborate path: a one-frame "delay buffer" shuffles every parameter
except ``AV``, ``TILT`` and ``T0`` by one frame, the parstochip is
written into the SPC packet queue, and ``hlframe.c`` performs the HL
→ LL parameter conversion (formant adjustment, ag/agf/agm gating,
etc.). The Python port collapses those stages: the one-frame delay
is currently a no-op (it shifts timing by 6.4 ms, audible only at
clause boundaries), and the HL → LL conversion is delegated to
sensible defaults until that port lands.

OUT_T0 holds the fundamental period in deciHz (10x Hz) when HLSyn
is enabled (``ph_drwt02.c`` line 1409); :class:`LLFrame.F0` uses
the same units, so the mapping is a direct copy. When OUT_T0 is
zero (the pre-pht0draw initial frames), we fall back to a default
122 Hz so the voicing source still produces output.
"""

from __future__ import annotations

from typing import Final

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_T0,
    OUT_TLT,
)
from dectalk.ph.parameter_tables import lineartilt

# Pre-pht0draw fallback: a 122 Hz adult-male F0 so voicing is audible
# while the PH module's F0 contour engine isn't running per-frame.
_DEFAULT_F0_DECIHZ: Final[int] = 1220

# Resting positions for fields parstochip doesn't carry. These match
# the LLFrame defaults so a freshly-constructed adapter output frame
# is identical to ``LLFrame()`` except for the PH-driven cells.
_DEFAULT_OQ: Final[int] = 50
_DEFAULT_SQ: Final[int] = 200
_DEFAULT_F4: Final[int] = 3500
_DEFAULT_B4: Final[int] = 250
_DEFAULT_F5: Final[int] = 4500
_DEFAULT_B5: Final[int] = 300
_DEFAULT_F6: Final[int] = 5500
_DEFAULT_B6: Final[int] = 500


def _clamp(value: int, lo: int, hi: int) -> int:
    """Saturating clamp.

    The PH module's per-frame trajectory smoothing assumes the C
    sender's pre-clamp at ``send_pars`` time. The Python port hasn't
    ported the full smoothing-stop conditions yet, so unbounded
    drift can push parameters past safe synthesizer ranges. Clamps
    here keep ``ll_synthesize`` from blowing up while parity work
    is still in progress.
    """
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def parstochip_to_llframe(parstochip: list[int]) -> LLFrame:
    """Build one :class:`LLFrame` from a populated parstochip array.

    Maps each ``OUT_*`` cell to the corresponding LLFrame field.
    Fields the PH module doesn't write (``F4..F6 / B4..B6 / OQ / SQ``,
    tracheal/nasal poles, parallel-voicing amps) keep their LLFrame
    defaults — these are tuned for a neutral adult-male voice.

    Args:
        parstochip: 1-D array of integers indexed by the ``OUT_*``
            constants from :mod:`dectalk.ph.param_indices`. Must be
            at least ``OUT_TLT + 1 = 9`` entries; phdraw allocates
            64 cells in practice.

    Returns:
        :class:`LLFrame` with PH-driven cells populated and the
        remaining cells at synthesizer-neutral defaults.
    """
    f0 = parstochip[OUT_T0] if parstochip[OUT_T0] > 0 else _DEFAULT_F0_DECIHZ

    # Spectral-tilt linearisation lookup, mirroring ph_claus.c line 735's
    # ``delaypars[OUT_TLT] = lineartilt[parstochip[OUT_TLT]]``. The PH
    # module's internal tilt scale (0..31) is remapped to the
    # synthesiser-side scale (0..40) via the 32-entry table from
    # ph_romi.c. Clamp the index to the table range first because
    # phdraw clamps tilt to 0..31 in C, but the smoothing-overflow
    # safety net in the Python port can occasionally produce a
    # higher raw value while the smoothing-stop conditions stay
    # un-ported.
    tilt_idx = _clamp(parstochip[OUT_TLT], 0, len(lineartilt) - 1)
    tl = lineartilt[tilt_idx]

    return LLFrame(
        F0=_clamp(f0, 500, 5000),  # 50-500 Hz in deciHz.
        AV=_clamp(parstochip[OUT_AV], 0, 80),
        Ah=_clamp(parstochip[OUT_AP], 0, 80),
        OQ=_DEFAULT_OQ,
        SQ=_DEFAULT_SQ,
        TL=tl,
        F1=_clamp(parstochip[OUT_F1], 100, 1300),
        B1=_clamp(parstochip[OUT_B1], 40, 1000),
        F2=_clamp(parstochip[OUT_F2], 500, 3000),
        B2=_clamp(parstochip[OUT_B2], 40, 1000),
        F3=_clamp(parstochip[OUT_F3], 1300, 4500),
        B3=_clamp(parstochip[OUT_B3], 40, 1000),
        F4=_DEFAULT_F4,
        B4=_DEFAULT_B4,
        F5=_DEFAULT_F5,
        B5=_DEFAULT_B5,
        F6=_DEFAULT_F6,
        B6=_DEFAULT_B6,
        FNZ=parstochip[OUT_FZ] if parstochip[OUT_FZ] > 0 else 270,
        # Parallel-formant noise amplitudes. The C side delivers
        # these as raw dB values; LLFrame's A2f..A6f use the same
        # scale.
        A2f=_clamp(parstochip[OUT_A2], 0, 80),
        A3f=_clamp(parstochip[OUT_A3], 0, 80),
        A4f=_clamp(parstochip[OUT_A4], 0, 80),
        A5f=_clamp(parstochip[OUT_A5], 0, 80),
        A6f=_clamp(parstochip[OUT_A6], 0, 80),
        Ab=_clamp(parstochip[OUT_AB], 0, 80),
    )


def parstochip_to_llframe_delayed(
    parstochip: list[int],
    previous_parstochip: list[int] | None,
) -> LLFrame:
    """One-frame-delayed LLFrame, mirroring ``send_pars()``'s delaybuf.

    Translates the ph_claus.c lines 706-820 delay-buffer pattern. The
    C source keeps a separate ``delaypars[]`` array that's filled
    incrementally: ``AV``, ``TILT`` and ``T0`` are taken from the
    current frame's ``parstochip[]`` (the freshly-computed values),
    while every other slot (``F1``, ``B1``, ``F2``, ``B2``, ``F3``,
    ``B3``, ``FZ``, ``A2``-``A6``, ``AB``, ``AP``) carries the
    *previous* frame's parstochip data. The net effect is that
    formant transitions arrive one frame later than the voicing /
    tilt / period changes that drive them.

    Args:
        parstochip: Current frame's parstochip array.
        previous_parstochip: Previous frame's parstochip, or
            ``None`` on the first call. ``None`` returns a frame
            with all the formant-side slots zero (matching the C
            source's ``initpardelay==0`` first-call path that
            outputs the unused delaypars seed with TLT=T0=AV=0
            and never spcwrite's it).

    Returns:
        :class:`LLFrame` populated with the skewed mix.
    """
    # The "previous" feed for F1..AP. Falling back to current
    # parstochip on the first call mirrors the C source's
    # behaviour of seeding delaypars with parstochip on the
    # very first frame (initpardelay loops on its return path).
    feed = previous_parstochip if previous_parstochip is not None else parstochip

    f0 = parstochip[OUT_T0] if parstochip[OUT_T0] > 0 else _DEFAULT_F0_DECIHZ
    tilt_idx = _clamp(parstochip[OUT_TLT], 0, len(lineartilt) - 1)
    tl = lineartilt[tilt_idx]

    return LLFrame(
        # Real-time slots from the current parstochip.
        F0=_clamp(f0, 500, 5000),
        AV=_clamp(parstochip[OUT_AV], 0, 80),
        TL=tl,
        # Delayed slots from the previous parstochip.
        Ah=_clamp(feed[OUT_AP], 0, 80),
        F1=_clamp(feed[OUT_F1], 100, 1300),
        B1=_clamp(feed[OUT_B1], 40, 1000),
        F2=_clamp(feed[OUT_F2], 500, 3000),
        B2=_clamp(feed[OUT_B2], 40, 1000),
        F3=_clamp(feed[OUT_F3], 1300, 4500),
        B3=_clamp(feed[OUT_B3], 40, 1000),
        FNZ=feed[OUT_FZ] if feed[OUT_FZ] > 0 else 270,
        A2f=_clamp(feed[OUT_A2], 0, 80),
        A3f=_clamp(feed[OUT_A3], 0, 80),
        A4f=_clamp(feed[OUT_A4], 0, 80),
        A5f=_clamp(feed[OUT_A5], 0, 80),
        A6f=_clamp(feed[OUT_A6], 0, 80),
        Ab=_clamp(feed[OUT_AB], 0, 80),
        # Synth-neutral fixed defaults.
        OQ=_DEFAULT_OQ,
        SQ=_DEFAULT_SQ,
        F4=_DEFAULT_F4,
        B4=_DEFAULT_B4,
        F5=_DEFAULT_F5,
        B5=_DEFAULT_B5,
        F6=_DEFAULT_F6,
        B6=_DEFAULT_B6,
    )


__all__ = ["parstochip_to_llframe", "parstochip_to_llframe_delayed"]
