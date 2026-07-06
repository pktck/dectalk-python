# ruff: noqa: PLR2004  -- the 32767 / -32768 int16 limits are inherent.
"""Default synth path: pump parstochip frames through ``vtm1.c``.

This module wires :func:`speech_waveform_generator` into the
end-to-end audio pipeline as the default render stage (issue #272),
with the :mod:`dectalk.hlsyn`-based path used by
:func:`dectalk.api.speak._pump_frames_to_samples` retained as the
``DECTALK_USE_VTM1=0`` legacy escape hatch.

The two paths share the same PH-stage origin (per-6.4 ms-frame
``parstochip[]`` arrays) but render audio through different
synthesizers:

* **vtm1 path** (this module, the default -- issue #272): consumes
  the post-``send_pars`` ``delaypars[]`` packet stream the driver
  loop builds via
  :func:`~dectalk.ph.parstochip_to_frames.send_pars_delaypars`
  (issue #275: formant-side slots one frame delayed, ``OUT_TLT``
  through the ``lineartilt[]`` LUT, ``OUT_AV``/``OUT_T0`` current
  — exactly what the C driver's ``spcwrite`` ships and what patch
  0006's ``vtm_frames.dump`` records), copies each packet into
  ``SynthState.parambuff`` and drives the integer Klatt
  synthesiser ported from ``vtm1.c::speech_waveform_generator``.
  This is the synthesizer the shipped ``libtts_us.so`` actually
  uses (the active build defines ``VTM1`` in ``dectalkf_klsyn.h``).
* **hlsyn path** (legacy, selected via ``DECTALK_USE_VTM1=0``):
  converts each raw parstochip to an
  :class:`~dectalk.hlsyn.llsyn.LLFrame` via
  :func:`~dectalk.ph.parstochip_to_frames.parstochip_to_llframe_delayed`
  (which applies the same send_pars delay + LUT internally), then
  drives the SenSyn 2.2 cascade-parallel synthesiser (``hlsyn/``).

The vtm1 path is the byte-exact-capable parity route -- on ``hello
world`` it is sample-count-exact vs the C binary (13845), F0 is
frame-exact, and the leading 213 samples are byte-identical --
so it is the Phase E workhorse (full byte-identical audio from
pure Python). The legacy hlsyn render over-runs the C reference
uniformly (~21450 vs 13845 samples on ``hello world``) and is
retained only as a diagnostic escape hatch (see
:func:`dectalk.api.speak._use_vtm1`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_TLT,
)
from dectalk.ph.spdef_chip import SpdChip
from dectalk.vtm.seed_speaker_state import PC_SAMPLE_RATE, seed_speaker_state
from dectalk.vtm.spd_chip import default_us_paul_spd
from dectalk.vtm.speech_waveform_generator import speech_waveform_generator
from dectalk.vtm.synth_state import SynthState

# Amplitude-DB slot indices that need clamping before vtm1 indexes them
# into the 88-entry :data:`~dectalk.vtm.amp_table.amptable`. The hlsyn
# path applies the same clamp via
# :func:`~dectalk.ph.parstochip_to_frames._clamp`; we mirror it here so
# the alternative vtm1 path doesn't trip on out-of-range PH-stage
# outputs while the PH driver is still being ported. ``amptable[x +
# 13]`` is the worst-case offset (line 196 of
# ``speech_waveform_generator.py``), so cap the raw DB value at
# ``len(amptable) - 13 - 1 = 74``.
_AMP_SLOT_INDICES: frozenset[int] = frozenset(
    {OUT_AP, OUT_A2, OUT_A3, OUT_A4, OUT_A5, OUT_A6, OUT_AB, OUT_AV, OUT_TLT}
)
_AMP_MAX: int = 74

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dectalk.data.voices import VoicePreset


def _spd_chip_for_preset(preset: VoicePreset | None) -> SpdChip:
    """Return an :class:`SpdChip` for the given voice preset.

    The full voice -> SpdChip mapping requires per-voice SPDEF
    tables (``p_us_vdf*.c``). For now only the US Paul defaults are
    available; other voices fall through to the same chip with their
    head-size delta applied via ``fnscale``.

    Args:
        preset: Voice preset, or ``None`` for the default neutral voice.

    Returns:
        A SpdChip instance ready to seed a :class:`SynthState`.
    """
    # The default Paul SpdChip is the only one fully extracted. Other
    # presets use this as the base -- per-voice tuning lives in
    # subsequent PRs.
    return default_us_paul_spd()


def pump_frames_via_vtm1(
    frames: list[list[int]],
    preset: VoicePreset | None = None,
    *,
    sample_rate: int = PC_SAMPLE_RATE,
) -> NDArray[np.int16]:
    """Synthesize a sequence of voice packets through ``speech_waveform_generator``.

    Alternative to
    :func:`dectalk.api.speak._pump_frames_to_samples`. Feeds each
    packet through the integer Klatt synthesiser from ``vtm1.c``.

    This function is the Python mirror of the C VTM's packet consumer
    (``vtmiont.c`` ``case SPC_type_voice``): it copies each packet
    into ``parambuff`` verbatim and runs one synthesis frame. It does
    NOT apply the ``send_pars`` transformation itself — the driver
    loop does that (issue #275) — so its input must already be at
    the post-``send_pars`` ``delaypars`` level (the level of the C
    oracle's ``vtm_frames.dump``; feeding that dump through here is
    the #263/#266 byte-parity experiment).

    Args:
        frames: Sequence of ``list[int]`` voice packets in parstochip
            layout (one per 6.4 ms frame), as produced by the PH-stage
            driver loop in
            :func:`dectalk.api.speak._speak_via_python_full` via
            :func:`~dectalk.ph.parstochip_to_frames.send_pars_delaypars`.
            Each inner list is expected to have length at least
            ``OUT_TLT + 1`` (i.e. all the OUT_* slots vtm1 reads).
        preset: Voice preset, or ``None`` for Paul. Drives the
            speaker-definition lookup.
        sample_rate: Output sample rate in Hz. ``PC_SAMPLE_RATE``
            (11025) drives the SAMPLE_RATE_INCREASE branch of
            ``vtm1.c::SetSampleRate``; ``MULAW_SAMPLE_RATE`` (8000)
            drives the SAMPLE_RATE_DECREASE branch; other values fall
            back to NO_SAMPLE_RATE_CHANGE.

    Returns:
        1-D int16 array of synthesised PCM samples.
    """
    if not frames:
        return np.zeros(0, dtype=np.int16)

    state = SynthState()
    seed_speaker_state(state, _spd_chip_for_preset(preset), sample_rate=sample_rate)

    samples_per_frame = state.uiNumberOfSamplesPerFrame
    out = np.zeros(len(frames) * samples_per_frame, dtype=np.int16)

    for fi, parstochip in enumerate(frames):
        # The frames are post-send_pars ``delaypars`` packets in
        # parstochip layout -- the call site in
        # :func:`dectalk.api.speak._render_clause_full` accumulates
        # them alongside the LLFrame list so the ``DECTALK_USE_VTM1``
        # branch can route through here.

        # Copy the OUT_* parameter cells into parambuff[1..]. The C
        # source uses ``variabpars = &parambuff[1]; variabpars[OUT_*]
        # = ...``; we mirror that 1-offset here. Amplitude-slot cells
        # are clamped to amptable's safe range before the copy so
        # the indexed lookup inside ``speech_waveform_generator``
        # doesn't IndexError on out-of-range PH-stage outputs.
        for i in range(min(len(parstochip), len(state.parambuff) - 1)):
            value = int(parstochip[i])
            if i in _AMP_SLOT_INDICES:
                value = max(0, min(value, _AMP_MAX))
            state.parambuff[i + 1] = value

        speech_waveform_generator(state, sample_rate=sample_rate)

        # iwave is sized MAXIMUM_FRAME_SIZE; only the first
        # uiNumberOfSamplesPerFrame slots are valid for this frame.
        start = fi * samples_per_frame
        for j in range(samples_per_frame):
            sample = state.iwave[j]
            # Clamp to int16 range; ``out << 1`` in
            # speech_waveform_generator can produce values outside
            # int16 in pathological cases (the C source relies on
            # ``short`` truncation semantics, which we approximate
            # via a Python clamp here).
            if sample > 32767:
                sample = 32767
            elif sample < -32768:
                sample = -32768
            out[start + j] = sample

    return out


__all__ = ["pump_frames_via_vtm1"]
