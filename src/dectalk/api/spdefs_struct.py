"""Public-facing SPDEFS speaker definition struct from ttsapi.h.

Translated from ``src/dapi/src/api/ttsapi.h``. ``SPDEFS`` is the
39-field voice descriptor returned by
``TextToSpeechGetSpeakerParams`` and accepted by
``TextToSpeechSetSpeakerParams``. Each field maps to one of the
``SPD_*`` parameter indices in :mod:`dectalk.include.cmd_codes`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Spdefs:
    """Public 39-field voice descriptor (matches C ``SPDEFS`` struct).

    Faithful translation of:

    .. code-block:: c

        typedef struct SPDEFS_TAG {
            short sex;                short smoothness;
            short assertiveness;      short average_pitch;
            ...   // 39 more shorts
        } SPDEFS;

    Field order matches the C struct so this dataclass can serve
    as a 1:1 stand-in when the Python API exposes
    ``TextToSpeechGetSpeakerParams``.

    Attributes:
        sex: 1 = male, 0 = female.
        smoothness: Spectral tilt offset, %.
        assertiveness: Final F0 fall, %.
        average_pitch: Average F0 in Hz.
        pitch_range: F0 range as % of Paul's range.
        breathiness: Breathiness in dB.
        richness: Richness % (controls open quotient).
        num_fixed_samp_og: Extra fixed samples in nopen.
        laryngealization: Laryngealisation %.
        head_size: Head size % of normal.
        formant4_res_freq: F4 cascade resonance frequency in Hz.
        formant4_bandwidth: F4 cascade bandwidth in Hz.
        formant5_res_freq: F5 cascade.
        formant5_bandwidth: F5 cascade bandwidth.
        parallel4_freq: P4 (parallel F4).
        parallel5_freq: P5.
        gain_frication: GF — frication-source gain (dB).
        gain_aspiration: GH — aspiration-source gain.
        gain_voicing: GV — voicing-source gain.
        gain_nasalization: GN — cascade nasal-pole input gain.
        gain_cfr1: G1 — cascade resonator 5 input gain.
        gain_cfr2: G2 — cascade resonator 4 input gain.
        gain_cfr3: G3 — cascade resonator 3 input gain.
        gain_cfr4: G4 — cascade resonator 2 input gain.
        loudness: LO — cascade 1st-formant gain (dB).
        spectral_tilt: FT — F0-dependent spectral tilt %.
        baseline_fall: BF — baseline F0 fall (Hz).
        lax_breathiness: LX — lax / voiceless breathiness.
        quickness: QU — quickness of larynx gestures %.
        hat_rise: HR — hat-pattern F0 rise (Hz).
        stress_rise: SR — max stress-rise F0 impulse (Hz).
        avg_glot_open: GS — glottal speed.
        avg_glot_voicd_open: For voiced obstruents.
        avg_glot_unv_open: For unvoiced obstruents.
        area_chink: Chink area (KLGLOT88).
        open_quo: Open-quotient slot.
        output_gain_mult: Output gain multiplier.
        junk: Reserved.
        junk1: Reserved.
    """

    sex: int = 0
    smoothness: int = 0
    assertiveness: int = 0
    average_pitch: int = 0
    pitch_range: int = 0
    breathiness: int = 0
    richness: int = 0
    num_fixed_samp_og: int = 0
    laryngealization: int = 0
    head_size: int = 0
    formant4_res_freq: int = 0
    formant4_bandwidth: int = 0
    formant5_res_freq: int = 0
    formant5_bandwidth: int = 0
    parallel4_freq: int = 0
    parallel5_freq: int = 0
    gain_frication: int = 0
    gain_aspiration: int = 0
    gain_voicing: int = 0
    gain_nasalization: int = 0
    gain_cfr1: int = 0
    gain_cfr2: int = 0
    gain_cfr3: int = 0
    gain_cfr4: int = 0
    loudness: int = 0
    spectral_tilt: int = 0
    baseline_fall: int = 0
    lax_breathiness: int = 0
    quickness: int = 0
    hat_rise: int = 0
    stress_rise: int = 0
    avg_glot_open: int = 0
    avg_glot_voicd_open: int = 0
    avg_glot_unv_open: int = 0
    area_chink: int = 0
    open_quo: int = 0
    output_gain_mult: int = 0
    junk: int = 0
    junk1: int = 0


__all__ = ["Spdefs"]
