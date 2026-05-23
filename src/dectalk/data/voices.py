"""Voice parameter tables for the 9 canonical DECtalk voices.

Each voice is described by:

- A :class:`dectalk.hlsyn.llsyn.Speaker` with appropriate sample rate,
  source shape, and gain settings.
- A baseline F0 (in tenths of a Hz, matching the C synthesizer's
  convention) which the per-frame builder copies into every voiced frame.
- A "head-size" multiplier that scales the formant frequencies of every
  phoneme. Perfect Paul is 1.00; Beautiful Betty (a smaller head) is
  ~1.18; Huge Harry (a larger head) is ~0.85; Kit the Kid (a child)
  is ~1.30.

These figures are calibrated approximations consistent with DECtalk's
documented voice inventory; the FONIX C tables are proprietary and not
redistributed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from dectalk.hlsyn.llsyn import Speaker
from dectalk.hlsyn.voice import SOURCE_NATURAL
from dectalk.include.dectalk import Voice


@dataclass(frozen=True, slots=True)
class VoicePreset:
    """Tunable parameters that distinguish one DECtalk voice from another.

    Attributes:
        voice: Voice ID enum value.
        speaker: Klatt :class:`Speaker` (sample rate, source shape, gains).
        f0_x10: Baseline fundamental frequency in tenths of a Hz.
        head_scale: Multiplier on every phoneme's formant frequencies.
            Smaller heads have higher formants (Betty, Kit), larger heads
            have lower formants (Harry).
        breathy: Open-quotient bias; bigger numbers give a breathier voice
            (Whispery Willy is the extreme).
    """

    voice: Voice
    speaker: Speaker
    f0_x10: int
    head_scale: float
    breathy: int


def _adult_male_speaker() -> Speaker:
    # ``UI=71`` matches the C reference's ``uiNumberOfSamplesPerFrame``
    # for 11.025 kHz (see ``vtm/set_sample_rate.py`` and the audit in
    # issue #152): the VTM's ``speech_waveform_generator`` consumes
    # frames of 71 samples (~6.4 ms), and PH ``allodurs[]`` are
    # calibrated in those 6.4 ms units. The pre-#152 value of 110
    # samples (~10 ms) stretched synthesis by ~55%.
    return Speaker(
        DU=0,
        UI=71,
        SR=11025,
        NF=5,
        SS=SOURCE_NATURAL,
        RS=8191,
        SB=0,
        CP=0,
        OS=0,
        GV=60,
        GH=50,
        GF=45,
    )


def _adult_female_speaker() -> Speaker:
    spkr = _adult_male_speaker()
    return Speaker(
        DU=spkr.DU,
        UI=spkr.UI,
        SR=spkr.SR,
        NF=spkr.NF,
        SS=spkr.SS,
        RS=spkr.RS,
        SB=spkr.SB,
        CP=spkr.CP,
        OS=spkr.OS,
        GV=spkr.GV - 4,
        GH=spkr.GH,
        GF=spkr.GF,
    )


def _child_speaker() -> Speaker:
    spkr = _adult_male_speaker()
    return Speaker(
        DU=spkr.DU,
        UI=spkr.UI,
        SR=spkr.SR,
        NF=spkr.NF,
        SS=spkr.SS,
        RS=spkr.RS,
        SB=spkr.SB,
        CP=spkr.CP,
        OS=spkr.OS,
        GV=spkr.GV - 6,
        GH=spkr.GH,
        GF=spkr.GF,
    )


# Canonical voice presets. The numeric F0 / head_scale / breathy values
# are reasonable, audibly distinct approximations; tuning to bit-exact
# DECtalk parity needs the proprietary FONIX voice tables.
PRESETS: Final[dict[str, VoicePreset]] = {
    "paul": VoicePreset(
        voice=Voice.PERFECT_PAUL,
        speaker=_adult_male_speaker(),
        f0_x10=1220,  # 122 Hz
        head_scale=1.00,
        breathy=50,
    ),
    "betty": VoicePreset(
        voice=Voice.BEAUTIFUL_BETTY,
        speaker=_adult_female_speaker(),
        f0_x10=2080,  # 208 Hz
        head_scale=1.18,
        breathy=55,
    ),
    "harry": VoicePreset(
        voice=Voice.HUGE_HARRY,
        speaker=_adult_male_speaker(),
        f0_x10=890,  # 89 Hz — booming low
        head_scale=0.85,
        breathy=45,
    ),
    "frank": VoicePreset(
        voice=Voice.FRAIL_FRANK,
        speaker=_adult_male_speaker(),
        f0_x10=1380,  # 138 Hz
        head_scale=0.95,
        breathy=70,  # frail = breathy + slow
    ),
    "dennis": VoicePreset(
        voice=Voice.DOCTOR_DENNIS,
        speaker=_adult_male_speaker(),
        f0_x10=1100,  # 110 Hz — deliberate, calm
        head_scale=1.05,
        breathy=48,
    ),
    "kit": VoicePreset(
        voice=Voice.KIT_THE_KID,
        speaker=_child_speaker(),
        f0_x10=2900,  # 290 Hz — child voice
        head_scale=1.30,
        breathy=55,
    ),
    "ursula": VoicePreset(
        voice=Voice.UPPITY_URSULA,
        speaker=_adult_female_speaker(),
        f0_x10=2300,  # 230 Hz
        head_scale=1.20,
        breathy=50,
    ),
    "rita": VoicePreset(
        voice=Voice.ROUGH_RITA,
        speaker=_adult_female_speaker(),
        f0_x10=1950,  # 195 Hz
        head_scale=1.12,
        breathy=60,
    ),
    "willy": VoicePreset(
        voice=Voice.WHISPERY_WILLY,
        speaker=_adult_male_speaker(),
        f0_x10=1180,  # 118 Hz
        head_scale=1.00,
        breathy=85,  # very breathy
    ),
}
"""Canonical voice id (``"paul"``..``"willy"``) -> :class:`VoicePreset`."""


def get_preset(name: str) -> VoicePreset:
    """Look up a voice preset by its short name (case-insensitive).

    Args:
        name: Short voice name (``"paul"``, ``"betty"``, ...).

    Returns:
        The :class:`VoicePreset` for the named voice.

    Raises:
        KeyError: If ``name`` is not a known voice.
    """
    return PRESETS[name.lower()]
