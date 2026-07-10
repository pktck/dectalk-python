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
    return Speaker(
        DU=0,
        UI=110,
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

# ``[:name X]`` accepts the C ``voice_names[]`` strings (``c_us_cde.h``
# lines 301-317), two of which differ from the preset keys above:
# ``wendy`` is the C-table name for the breathy female row exposed here
# as ``willy`` (see ``dectalk.ph.voice_definitions.VOICES_BY_NAME``),
# and ``val`` (Variable Val, speaker 9) defaults to the current-speaker
# row -- Paul on a fresh handle -- until a ``[:dv save]`` overwrites it
# (``ph_vset.c`` ``saveval``). Discovered via the issue #316 command
# grid: ``[:name wendy]`` / ``[:name val]`` crashed with KeyError while
# ``[:nw]`` / ``[:nv]`` rendered byte-exact.
_NAME_ALIASES: Final[dict[str, str]] = {
    "wendy": "willy",
    "val": "paul",
}


def get_preset(name: str) -> VoicePreset:
    """Look up a voice preset by its short name (case-insensitive).

    Args:
        name: Short voice name (``"paul"``, ``"betty"``, ...) or a
            documented ``[:name X]`` alias (``"wendy"``, ``"val"``).

    Returns:
        The :class:`VoicePreset` for the named voice.

    Raises:
        KeyError: If ``name`` is not a known voice.
    """
    key = name.lower()
    return PRESETS[_NAME_ALIASES.get(key, key)]
