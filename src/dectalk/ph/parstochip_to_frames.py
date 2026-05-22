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
etc.). The Python port now provides two paths:

- :func:`parstochip_to_llframe_delayed` — the legacy direct-copy path
  (no HL→LL gating). Still the default for the full pipeline driver.
- :func:`parstochip_to_llframe_via_hl` — the new path that builds an
  :class:`~dectalk.ph.hlsyn_structs.HLFrame` from parstochip and runs
  the full :func:`~dectalk.hlsyn.hlframe.hl_synthesize_ll_frame`
  conversion (AV/AH/AF gating, formant bandwidth adjustments, OQ/TL/DI).

OUT_T0 holds the fundamental period in deciHz (10x Hz) when HLSyn
is enabled (``ph_drwt02.c`` line 1409); :class:`LLFrame.F0` uses
the same units, so the mapping is a direct copy. When OUT_T0 is
zero (the pre-pht0draw initial frames), we fall back to a default
122 Hz so the voicing source still produces output.
"""

from __future__ import annotations

from typing import Final

from dectalk.hlsyn.hlframe import hl_synthesize_ll_frame
from dectalk.hlsyn.initialize_hl_synthesizer import initialize_hl_synthesizer
from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_ABLADE,
    OUT_AG,
    OUT_AL,
    OUT_AN,
    OUT_AP,
    OUT_ATB,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_CNK,
    OUT_DC,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_F4,
    OUT_FZ,
    OUT_PLACE,
    OUT_PS,
    OUT_T0,
    OUT_TLT,
    OUT_UE,
)
from dectalk.ph.parameter_tables import lineartilt

# Pre-pht0draw fallback: a 122 Hz adult-male F0 so voicing is audible
# while the PH module's F0 contour engine isn't running per-frame.
_DEFAULT_F0_DECIHZ: Final[int] = 1220

# 16-bit signed wrap constants for the vtmiont.c ``(short)`` reinterpret
# casts on OUT_UE / OUT_DC / OUT_ATB / OUT_PLACE.
_INT16_MASK: Final[int] = 0xFFFF
_INT16_SIGN_BIT: Final[int] = 0x8000
_INT16_WRAP: Final[int] = 0x10000

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


def _to_int16(value: int) -> int:
    """Reinterpret the low 16 bits of ``value`` as a signed int16.

    The C reader at ``vtmiont.c:725-746`` casts several parstochip cells
    via ``(short)`` before scaling — ``OUT_UE``, ``OUT_DC``, ``OUT_ATB``,
    ``OUT_PLACE``. The Python parstochip carries arbitrary-precision int
    values, so a sign-aware reinterpret-cast is needed to mirror the C
    behaviour for cells whose raw integer can be negative.
    """
    masked = value & _INT16_MASK
    return masked - _INT16_WRAP if masked >= _INT16_SIGN_BIT else masked


def _build_hl_frame_from_parstochip(parstochip: list[int]) -> HLFrame:
    """Build an :class:`~dectalk.ph.hlsyn_structs.HLFrame` from parstochip.

    Extracts the NEW_VTM HLSyn slots (``OUT_AG``, ``OUT_AL``, ``OUT_ABLADE``,
    ``OUT_AN``, ``OUT_ATB``, ``OUT_PS``, ``OUT_CNK``, ``OUT_DC``, ``OUT_UE``,
    ``OUT_PLACE``) and the classic formant / F0 slots, converting integer
    parstochip values to the float fields HLFrame uses.

    Unit conversions mirror the canonical SPC-frame → HLFrame reader in
    ``vtm/vtmiont.c:720-750`` (HLSYN build) — phdraw writes areas as raw
    "x100" / "x10" scaled integers (`ph_draw.c:4159, 4280, 4282`) and the
    reader recovers the float-mm² (or cmH2O) values via these factors:

    +----------------+------------------+----------------+
    | HLFrame field  | C reader scale   | Source cell    |
    +================+==================+================+
    | ``ag``         | ``* 0.01f``      | ``OUT_AG``     |
    | ``al``         | ``* 0.1f``       | ``OUT_AL``     |
    | ``ab``         | ``* 0.1f``       | ``OUT_ABLADE`` |
    | ``ap``         | ``* 0.01f``      | ``OUT_CNK``    |
    | ``an``         | ``* 0.1f``       | ``OUT_AN``     |
    | ``ue``         | ``(short)…``     | ``OUT_UE``     |
    | ``ps``         | ``* 0.01f``      | ``OUT_PS``     |
    | ``dc``         | ``(short)…``     | ``OUT_DC``     |
    | ``atb``        | ``(short)…*0.1f``| ``OUT_ATB``    |
    | ``place``      | ``(short)…``     | ``OUT_PLACE``  |
    | ``f0``         | direct           | ``OUT_T0``     |
    | ``f1/f2/f3``   | direct           | ``OUT_F1..F3`` |
    | ``f4``         | direct           | ``OUT_F4``     |
    +----------------+------------------+----------------+

    ``T0`` (fundamental period) is stored in deciHz (10x Hz) by phdraw in
    the HLSYN build (``ph_drwt02.c:1406-1410``); ``HLFrame.f0`` uses the
    same deciHz units, so the mapping is a direct copy.

    Args:
        parstochip: Integer array indexed by ``OUT_*`` constants. Must be
            at least ``OUT_PLACE + 1 = 38`` entries for NEW_VTM slots;
            shorter arrays fall back to 0.0 for out-of-range indices.

    Returns:
        Freshly constructed :class:`~dectalk.ph.hlsyn_structs.HLFrame`.
    """
    n = len(parstochip)

    def _safe(idx: int, default: int = 0) -> int:
        return parstochip[idx] if idx < n else default

    return HLFrame(
        ag=_safe(OUT_AG) * 0.01,
        al=_safe(OUT_AL) * 0.1,
        ab=_safe(OUT_ABLADE) * 0.1,
        an=_safe(OUT_AN) * 0.1,
        # vtmiont.c line 728: frame.ap is read from OUT_CNK (chink area,
        # mm²*100), NOT OUT_AP. The OUT_AP cell carries aspiration
        # amplitude in dB and is consumed by the Ah path in the delayed
        # adapter; mixing them here would silence the HL→LL voicing gate.
        ap=_safe(OUT_CNK) * 0.01,
        # OUT_ATB is a signed quantity (post-CNK adjustments can drive
        # it negative); mirror the ``(short)`` cast in vtmiont.c:738.
        atb=_to_int16(_safe(OUT_ATB)) * 0.1,
        ps=_safe(OUT_PS) * 0.01,
        # OUT_DC / OUT_UE flow through (short) casts in vtmiont.c:730/737
        # without further scaling; preserve the sign behaviour.
        dc=float(_to_int16(_safe(OUT_DC))),
        ue=float(_to_int16(_safe(OUT_UE))),
        # OUT_PLACE is a signed cast with no scale (vtmiont.c:744).
        place=_to_int16(_safe(OUT_PLACE)),
        f0=float(parstochip[OUT_T0] if parstochip[OUT_T0] > 0 else _DEFAULT_F0_DECIHZ),
        f1=float(_clamp(parstochip[OUT_F1], 100, 1300)),
        f2=float(_clamp(parstochip[OUT_F2], 500, 3000)),
        f3=float(_clamp(parstochip[OUT_F3], 1300, 4500)),
        f4=float(_safe(OUT_F4, _DEFAULT_F4)),
    )


def _build_hl_state_from_parstochip(
    parstochip: list[int],
    speaker: HLSpeaker,
) -> HLState:
    """Approximate :class:`~dectalk.ph.hlsyn_structs.HLState` from parstochip.

    Because SpeechCircuit (``circuit.c``) is not yet ported, we cannot solve
    for the aerodynamic running state (mouth pressure ``Pm``, exact glottal
    flow area ``agx`` / ``agf``) from first principles.  Instead we use the
    glottal area that phdraw already computed:

    - ``state.agf = state.agx = parstochip[OUT_AG]`` (mm^2).
    - ``state.Pm = 0`` (no mouth pressure when SpeechCircuit is shimmed).
    - ``state.f1c = 0`` (tongue_acx_f1c in hl_synthesize_ll_frame fills it).
    - ``state.f1x = 0``, ``state.b1x = 0`` (filled by hl_synthesize_ll_frame
      after tongue_acx_f1c runs; the shim checks for zero and falls back to
      frame.f1 / speaker.B1m).

    Args:
        parstochip: Integer array indexed by ``OUT_*`` constants.
        speaker: Initialized :class:`~dectalk.ph.hl_speaker.HLSpeaker`
            (used for ``loc`` initialization if needed).

    Returns:
        Freshly constructed :class:`~dectalk.ph.hlsyn_structs.HLState`.
    """
    # OUT_AG is stored as mm²*100 by phdraw; scale to mm² to match the
    # vtmiont.c reader so state.agx / state.agf comparisons against
    # speaker.agm (mm²) sit in the right magnitude band.
    ag = parstochip[OUT_AG] * 0.01 if len(parstochip) > OUT_AG else 0.0
    state = HLState()
    state.agx = ag
    state.agf = ag
    state.Pm = 0.0
    state.f1c = 0.0
    state.f1x = 0.0
    state.b1x = 0.0
    return state


def parstochip_to_llframe_via_hl(
    parstochip: list[int],
    previous_parstochip: list[int] | None,
    speaker: HLSpeaker | None = None,
) -> LLFrame:
    """Build a :class:`LLFrame` via the full HL→LL conversion path.

    Constructs an :class:`~dectalk.ph.hlsyn_structs.HLFrame` from the
    current parstochip, builds an approximated
    :class:`~dectalk.ph.hlsyn_structs.HLState`, and calls
    :func:`~dectalk.hlsyn.hlframe.hl_synthesize_ll_frame` to run the full
    AV/AH/AF gating, formant bandwidth adjustments, OQ/TL/DI computation.

    The one-frame delay (``AV``, ``T0``, ``TLT`` from the current frame;
    formant slots from the previous) mirrors :func:`parstochip_to_llframe_delayed`.

    Args:
        parstochip: Current frame's integer parstochip.
        previous_parstochip: Previous frame's parstochip, or ``None`` on the
            first call (falls back to the current frame for formant slots).
        speaker: :class:`~dectalk.ph.hl_speaker.HLSpeaker` to use; defaults
            to the module-level male singleton initialized from ``inithl.c``.

    Returns:
        :class:`LLFrame` produced by the HL→LL mapper.
    """
    if speaker is None:
        speaker, _oldframe, _oldstate = initialize_hl_synthesizer(is_male=True)

    feed = previous_parstochip if previous_parstochip is not None else parstochip

    # Build HLFrame: "real-time" fields from current parstochip, delayed
    # formant fields from the previous frame, matching the delay-buffer pattern
    # in send_pars().
    frame = _build_hl_frame_from_parstochip(parstochip)
    # Override F1/F2/F3 from the delayed feed.
    frame.f1 = float(_clamp(feed[OUT_F1], 100, 1300))
    frame.f2 = float(_clamp(feed[OUT_F2], 500, 3000))
    frame.f3 = float(_clamp(feed[OUT_F3], 1300, 4500))
    # Areas from the delayed feed need the same unit conversions as the
    # current-frame path in _build_hl_frame_from_parstochip (vtmiont.c:725-730).
    if len(feed) > OUT_AG:
        frame.ag = feed[OUT_AG] * 0.01
    if len(feed) > OUT_AN:
        frame.an = feed[OUT_AN] * 0.1
    if len(feed) > OUT_CNK:
        frame.ap = feed[OUT_CNK] * 0.01

    # Use current parstochip for oldframe as well (best approximation without
    # a full running state history; see SpeechCircuit shim in hlframe.py).
    oldframe = _build_hl_frame_from_parstochip(parstochip)

    state = _build_hl_state_from_parstochip(feed, speaker)
    oldstate = _build_hl_state_from_parstochip(parstochip, speaker)

    return hl_synthesize_ll_frame(frame, oldframe, speaker, state, oldstate)


__all__ = [
    "parstochip_to_llframe",
    "parstochip_to_llframe_delayed",
    "parstochip_to_llframe_via_hl",
]
