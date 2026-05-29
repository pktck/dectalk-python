"""US English voice-definition tables.

Translated from ``src/dapi/src/ph/p_us_vdf.c`` — the per-voice parameter
arrays the C library indexes into when the cmd handler runs ``[:nb]``,
``[:nh]``, etc. Each entry is the 33-field voice struct:

  0  SEX (1=MALE, 0=FEMALE)
  1  SM smoothness (spectral tilt offset, %)
  2  AS assertiveness (final F0 fall, %)
  3  AP average pitch (Hz)
  4  PR pitch range (% of Paul's range)
  5  BR breathiness (dB)
  6  RI richness (%, nopen = 100-RI % of T0)
  7  NF additional fixed samples in nopen
  8  LA laryngealization (%)
  9  HS head size (% of normal for SEX)
 10  F4 cascade 4th formant freq (Hz)
 11  B4 cascade 4th formant bandwidth (Hz)
 12  F5 cascade 5th formant freq
 13  B5 cascade 5th formant bandwidth
 14  F7 parallel 4th formant freq
 15  F8 parallel 5th formant freq
 16  GF frication source gain (dB)
 17  GH aspiration source gain (dB)
 18  GV voicing source gain (dB)
 19  GN cascade nasal pole input gain (dB)
 20  G1 cascade 5th formant input gain (dB)
 21  G2 cascade 4th formant input gain (dB)
 22  G3 cascade 3rd formant input gain (dB)
 23  G4 cascade 2nd formant input gain (dB)
 24  LO loudness (cascade 1st formant gain in dB)
 25  FT F0-dependent spectral tilt (% of max)
 26  BF baseline F0 fall (Hz)
 27  LX lax-folds-adjacent-voiceless breathiness
 28  QU quickness of larynx gestures (% of max)
 29  HR hat-pattern F0 rise (Hz)
 30  SR max stress-rise F0 impulse height (Hz)
 31  GS glottal speed
 32  output gain multiplier

Parsed for the Linux build (FP_VTM undefined). The C struct is
SPDEF=39 ints; the initialiser fills 33, the remaining 6 default
to 0.
"""

from __future__ import annotations

from typing import Final

from dectalk.api.spdefs_struct import Spdefs

voice_paul: Final[tuple[int, ...]] = (
    1,
    3,
    100,
    # AP (average pitch, Hz). The C ``paul_8[SPDEF]`` row uses 122
    # (p_us_vdf_dectalk43.c:8); this had been transcribed as 100, which
    # dropped the Python pipeline's baseline F0 ~30 Hz below the C
    # oracle (issue #220 fault 1).
    122,
    100,
    0,
    70,
    0,
    0,
    100,
    3300,
    260,
    3650,
    330,
    3350,
    3850,
    67,
    67,
    68,
    72,
    71,
    60,
    50,
    67,
    81,
    75,
    18,
    0,
    40,
    18,
    32,
    0,
    -1,
)

voice_chris: Final[tuple[int, ...]] = (
    1,
    3,
    100,
    100,
    100,
    0,
    70,
    0,
    0,
    100,
    3300,
    260,
    3650,
    330,
    3350,
    3850,
    67,
    67,
    68,
    72,
    71,
    60,
    50,
    67,
    81,
    75,
    18,
    0,
    40,
    18,
    32,
    0,
    -1,
)

voice_betty: Final[tuple[int, ...]] = (
    0,
    4,
    35,
    208,
    240,
    0,
    40,
    0,
    0,
    100,
    4450,
    260,
    6000,
    6000,
    4100,
    6000,
    69,
    67,
    68,
    72,
    69,
    67,
    52,
    60,
    75,
    75,
    0,
    80,
    55,
    14,
    20,
    0,
    -1,
)

voice_harry: Final[tuple[int, ...]] = (
    1,
    12,
    100,
    89,
    80,
    0,
    86,
    10,
    0,
    115,
    3300,
    200,
    3850,
    240,
    3200,
    4000,
    68,
    67,
    68,
    72,
    71,
    61,
    52,
    67,
    76,
    60,
    9,
    0,
    10,
    20,
    30,
    0,
    -3,
)

voice_frank: Final[tuple[int, ...]] = (
    1,
    46,
    65,
    155,
    90,
    50,
    40,
    0,
    5,
    90,
    3650,
    280,
    4200,
    300,
    3500,
    4050,
    68,
    68,
    68,
    73,
    74,
    61,
    56,
    71,
    73,
    100,
    9,
    50,
    0,
    20,
    22,
    0,
    3,
)

voice_kit: Final[tuple[int, ...]] = (
    0,
    5,
    65,
    296,
    180,
    47,
    70,
    0,
    0,
    77,
    6000,
    6000,
    6000,
    6000,
    4450,
    6000,
    58,
    70,
    68,
    72,
    69,
    69,
    50,
    55,
    68,
    75,
    0,
    75,
    50,
    20,
    22,
    0,
    -1,
)

voice_ursula: Final[tuple[int, ...]] = (
    0,
    60,
    100,
    240,
    135,
    0,
    100,
    10,
    0,
    95,
    4450,
    260,
    6000,
    6000,
    4300,
    6000,
    68,
    67,
    68,
    73,
    69,
    75,
    53,
    60,
    68,
    100,
    8,
    50,
    30,
    20,
    32,
    0,
    0,
)

voice_rita: Final[tuple[int, ...]] = (
    0,
    24,
    65,
    106,
    80,
    46,
    20,
    0,
    4,
    95,
    4000,
    250,
    6000,
    6000,
    4100,
    6000,
    67,
    66,
    68,
    72,
    69,
    72,
    47,
    61,
    76,
    0,
    0,
    0,
    30,
    20,
    32,
    0,
    -3,
)

voice_wendy: Final[tuple[int, ...]] = (
    0,
    100,
    50,
    200,
    175,
    55,
    0,
    10,
    0,
    100,
    4500,
    400,
    6000,
    6000,
    4100,
    6000,
    70,
    68,
    68,
    75,
    69,
    71,
    57,
    60,
    70,
    100,
    0,
    80,
    10,
    20,
    22,
    0,
    6,
)

voice_dennis: Final[tuple[int, ...]] = (
    1,
    100,
    100,
    110,
    125,
    38,
    0,
    10,
    0,
    105,
    3200,
    240,
    3600,
    280,
    4100,
    6000,
    68,
    68,
    68,
    75,
    76,
    65,
    51,
    71,
    70,
    100,
    9,
    70,
    50,
    10,
    22,
    0,
    -3,
)

# Voice presets indexed by speaker ID (matches voice_names order).
voices: Final[tuple[tuple[int, ...], ...]] = (
    voice_paul,
    voice_chris,
    voice_betty,
    voice_harry,
    voice_frank,
    voice_kit,
    voice_ursula,
    voice_rita,
    voice_wendy,
    voice_dennis,
)

# Name-keyed lookup mirroring :data:`dectalk.data.voices.PRESETS`. The
# C ``p_us_vdf_dectalk43.c`` file declares one ``const short
# <name>[SPDEF]`` per voice; this map keeps the row addressable by the
# same lower-case name the public API uses (``"paul"``..``"dennis"``).
# ``"chris"`` aliases ``voice_chris`` (identical row to ``voice_paul``
# in the v43 table). Wendy and Willy are *not* one-to-one in the v43
# table (the public API exposes Willy via the breathy preset; the C
# voice-table row used in the binary tree is ``wendy_8``), so we map
# the public ``"willy"`` name to ``voice_wendy`` -- the only female
# breathy-tradition row in the table -- to keep the public preset
# names round-trippable through the Spdefs scaling.
VOICES_BY_NAME: Final[dict[str, tuple[int, ...]]] = {
    "paul": voice_paul,
    "betty": voice_betty,
    "harry": voice_harry,
    "frank": voice_frank,
    "dennis": voice_dennis,
    "kit": voice_kit,
    "ursula": voice_ursula,
    "rita": voice_rita,
    "willy": voice_wendy,
    "chris": voice_chris,
    "wendy": voice_wendy,
}


def voice_tuple_to_spdefs(row: tuple[int, ...]) -> Spdefs:
    """Convert a raw 33-int voice row into an :class:`Spdefs` dataclass.

    The C ``SPDEF`` struct is 39 ints; the per-voice initialiser fills
    the first 33 and leaves the remaining 6 (``avg_glot_open``,
    ``avg_glot_voicd_open``, ``avg_glot_unv_open``, ``area_chink``,
    ``open_quo``, ``output_gain_mult``) zero-defaulted. The Python
    ``Spdefs`` dataclass matches the C field order exactly, so the
    mapping is positional.

    Args:
        row: A 33-int (or shorter) tuple from one of the
            ``voice_<name>`` constants in this module.

    Returns:
        An :class:`Spdefs` instance with the first ``len(row)`` fields
        populated from ``row`` and the remainder left at their zero
        defaults.
    """
    # ``output_gain_mult`` sits at index 32 in the C initialiser; the
    # zero-defaulted tail (junk / junk1 / etc.) is unchanged from the
    # dataclass default.
    return Spdefs(
        sex=row[0],
        smoothness=row[1],
        assertiveness=row[2],
        average_pitch=row[3],
        pitch_range=row[4],
        breathiness=row[5],
        richness=row[6],
        num_fixed_samp_og=row[7],
        laryngealization=row[8],
        head_size=row[9],
        formant4_res_freq=row[10],
        formant4_bandwidth=row[11],
        formant5_res_freq=row[12],
        formant5_bandwidth=row[13],
        parallel4_freq=row[14],
        parallel5_freq=row[15],
        gain_frication=row[16],
        gain_aspiration=row[17],
        gain_voicing=row[18],
        gain_nasalization=row[19],
        gain_cfr1=row[20],
        gain_cfr2=row[21],
        gain_cfr3=row[22],
        gain_cfr4=row[23],
        loudness=row[24],
        spectral_tilt=row[25],
        baseline_fall=row[26],
        lax_breathiness=row[27],
        quickness=row[28],
        hat_rise=row[29],
        stress_rise=row[30],
        avg_glot_open=row[31],
        output_gain_mult=row[32],
    )


def spdefs_for_voice(name: str | None) -> Spdefs:
    """Return the :class:`Spdefs` scalar table for a public voice name.

    Falls back to Paul when ``name`` is ``None`` (matching the C
    library's default-voice behaviour: a fresh kernel handle starts in
    ``CURRENT_PAUL`` per ``ttsapi.c``'s ``LoadStartupVoice`` path).
    Unknown names also fall back to Paul rather than raising; the
    public-API surface in :func:`dectalk.speak` already validates voice
    names against :data:`dectalk.data.voices.PRESETS`, so any name that
    reaches this layer has already been checked.

    Args:
        name: A canonical voice name (``"paul"``..``"willy"``,
            ``"chris"``, ``"wendy"``). Case-insensitive. ``None`` is
            treated as Paul.

    Returns:
        An :class:`Spdefs` instance representing the requested voice's
        per-scalar parameters.
    """
    if name is None:
        return voice_tuple_to_spdefs(voice_paul)
    row = VOICES_BY_NAME.get(name.lower(), voice_paul)
    return voice_tuple_to_spdefs(row)


__all__ = [
    "VOICES_BY_NAME",
    "spdefs_for_voice",
    "voice_betty",
    "voice_chris",
    "voice_dennis",
    "voice_frank",
    "voice_harry",
    "voice_kit",
    "voice_paul",
    "voice_rita",
    "voice_tuple_to_spdefs",
    "voice_ursula",
    "voice_wendy",
    "voices",
]
