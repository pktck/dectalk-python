"""US English voice-definition tables.

Translated from ``src/dapi/src/ph/p_us_vdf_dectalk43.c`` — the per-voice
parameter arrays the C library indexes into when the cmd handler runs
``[:nb]``, ``[:nh]``, etc. This is the *active* voice table: the linked
binary compiles ``p_us_vdf_dectalk43.c`` (confirmed by the build's
``ph_vdefi.d`` dependency list, i.e. ``VDF_DECTALK_43`` is defined and
``HLSYN`` is not), and at the US sample rate (11025 Hz, ``>= 8763``)
``ph_vset.c:454-457`` selects the non-``_8`` ``voidef[voice]`` rows
(``ph_main.c:461`` wires ``voidef[0] = (short*)paul``). The older
``p_us_vdf.c`` reference and the ``_8`` (``< 8763`` Hz) rows are *not*
the live path.

Each entry is the 33-field voice struct:

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
 31  GS glottal speed (``AGO`` / avg_glot_open slot)
 32  output gain multiplier

Parsed for the Linux build (FP_VTM undefined). The C ``SPDEF`` struct
is 39 ints. In ``p_us_vdf_dectalk43.c`` the per-voice initialiser fills
38 slots: indices 0..30 are ``SEX``..``SR``, index 31 is ``AGO`` and
indices 32..37 are ``agvo``/``aguo``/``unvow``/``chink``/``open_quo``/
``OutputGainMult`` — *all zero for every dectalk43 voice*. The 33-field
Python row keeps the historical convention (index 31 = glottal speed,
index 32 = output gain multiplier); because the dectalk43 output-gain
multiplier (C index 37) and every slot in 32..37 are zero, index 32
is 0 for all ten voices. (The retired ``p_us_vdf.c`` reference packed
the FP_VTM output-gain multiplier directly at index 32, hence the old
``-1``/``-3``/``+6`` values; that file is not compiled.)
"""

from __future__ import annotations

from typing import Final

from dectalk.api.spdefs_struct import Spdefs

voice_paul: Final[tuple[int, ...]] = (
    1,  #  0 SEX
    3,  #  1 SM
    100,  #  2 AS
    122,  #  3 AP
    100,  #  4 PR
    0,  #  5 BR
    70,  #  6 RI
    0,  #  7 NF
    0,  #  8 LA
    100,  #  9 HS
    3300,  # 10 F4
    260,  # 11 B4
    3650,  # 12 F5
    330,  # 13 B5
    3350,  # 14 F7
    3850,  # 15 F8
    70,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    74,  # 19 GN
    68,  # 20 G1
    60,  # 21 G2
    48,  # 22 G3
    64,  # 23 G4
    86,  # 24 LO
    75,  # 25 FT
    18,  # 26 BF
    0,  # 27 LX
    40,  # 28 QU
    18,  # 29 HR
    32,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

# Crusty Chris is identical to Perfect Paul in the dectalk43 table
# (p_us_vdf_dectalk43.c has no ``chris`` row of its own; the binary's
# voice directory points the chris slot at the paul row).
voice_chris: Final[tuple[int, ...]] = voice_paul

voice_betty: Final[tuple[int, ...]] = (
    0,  #  0 SEX
    4,  #  1 SM
    35,  #  2 AS
    208,  #  3 AP
    240,  #  4 PR
    0,  #  5 BR
    40,  #  6 RI
    0,  #  7 NF
    0,  #  8 LA
    100,  #  9 HS
    4450,  # 10 F4
    260,  # 11 B4
    6000,  # 12 F5
    6000,  # 13 B5
    4100,  # 14 F7
    6000,  # 15 F8
    72,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    72,  # 19 GN
    69,  # 20 G1
    65,  # 21 G2
    50,  # 22 G3
    56,  # 23 G4
    81,  # 24 LO
    75,  # 25 FT
    0,  # 26 BF
    80,  # 27 LX
    55,  # 28 QU
    14,  # 29 HR
    20,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_harry: Final[tuple[int, ...]] = (
    1,  #  0 SEX
    12,  #  1 SM
    100,  #  2 AS
    89,  #  3 AP
    80,  #  4 PR
    0,  #  5 BR
    86,  #  6 RI
    10,  #  7 NF
    0,  #  8 LA
    115,  #  9 HS
    3300,  # 10 F4
    200,  # 11 B4
    3850,  # 12 F5
    240,  # 13 B5
    3200,  # 14 F7
    4000,  # 15 F8
    70,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    73,  # 19 GN
    71,  # 20 G1
    60,  # 21 G2
    52,  # 22 G3
    62,  # 23 G4
    81,  # 24 LO
    60,  # 25 FT
    9,  # 26 BF
    0,  # 27 LX
    10,  # 28 QU
    20,  # 29 HR
    30,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_frank: Final[tuple[int, ...]] = (
    1,  #  0 SEX
    46,  #  1 SM
    65,  #  2 AS
    155,  #  3 AP
    90,  #  4 PR
    50,  #  5 BR
    40,  #  6 RI
    0,  #  7 NF
    5,  #  8 LA
    90,  #  9 HS
    3650,  # 10 F4
    280,  # 11 B4
    4200,  # 12 F5
    300,  # 13 B5
    3500,  # 14 F7
    4050,  # 15 F8
    68,  # 16 GF
    68,  # 17 GH
    63,  # 18 GV
    75,  # 19 GN
    63,  # 20 G1
    58,  # 21 G2
    56,  # 22 G3
    66,  # 23 G4
    86,  # 24 LO
    100,  # 25 FT
    9,  # 26 BF
    50,  # 27 LX
    0,  # 28 QU
    20,  # 29 HR
    22,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_kit: Final[tuple[int, ...]] = (
    0,  #  0 SEX
    5,  #  1 SM
    65,  #  2 AS
    306,  #  3 AP
    210,  #  4 PR
    47,  #  5 BR
    40,  #  6 RI
    0,  #  7 NF
    0,  #  8 LA
    80,  #  9 HS
    6000,  # 10 F4
    6000,  # 11 B4
    6000,  # 12 F5
    6000,  # 13 B5
    4450,  # 14 F7
    6000,  # 15 F8
    72,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    71,  # 19 GN
    69,  # 20 G1
    69,  # 21 G2
    52,  # 22 G3
    50,  # 23 G4
    73,  # 24 LO
    75,  # 25 FT
    0,  # 26 BF
    75,  # 27 LX
    50,  # 28 QU
    20,  # 29 HR
    22,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_ursula: Final[tuple[int, ...]] = (
    0,  #  0 SEX
    60,  #  1 SM
    100,  #  2 AS
    240,  #  3 AP
    135,  #  4 PR
    0,  #  5 BR
    100,  #  6 RI
    10,  #  7 NF
    0,  #  8 LA
    95,  #  9 HS
    4450,  # 10 F4
    260,  # 11 B4
    6000,  # 12 F5
    6000,  # 13 B5
    4300,  # 14 F7
    6000,  # 15 F8
    70,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    74,  # 19 GN
    67,  # 20 G1
    65,  # 21 G2
    51,  # 22 G3
    58,  # 23 G4
    80,  # 24 LO
    100,  # 25 FT
    8,  # 26 BF
    50,  # 27 LX
    30,  # 28 QU
    20,  # 29 HR
    32,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_rita: Final[tuple[int, ...]] = (
    0,  #  0 SEX
    24,  #  1 SM
    65,  #  2 AS
    106,  #  3 AP
    80,  #  4 PR
    46,  #  5 BR
    20,  #  6 RI
    0,  #  7 NF
    4,  #  8 LA
    95,  #  9 HS
    4000,  # 10 F4
    250,  # 11 B4
    6000,  # 12 F5
    6000,  # 13 B5
    4100,  # 14 F7
    6000,  # 15 F8
    72,  # 16 GF
    70,  # 17 GH
    65,  # 18 GV
    73,  # 19 GN
    69,  # 20 G1
    72,  # 21 G2
    48,  # 22 G3
    54,  # 23 G4
    83,  # 24 LO
    0,  # 25 FT
    0,  # 26 BF
    0,  # 27 LX
    30,  # 28 QU
    20,  # 29 HR
    32,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_wendy: Final[tuple[int, ...]] = (
    0,  #  0 SEX
    100,  #  1 SM
    50,  #  2 AS
    200,  #  3 AP
    175,  #  4 PR
    55,  #  5 BR
    0,  #  6 RI
    10,  #  7 NF
    0,  #  8 LA
    100,  #  9 HS
    4500,  # 10 F4
    400,  # 11 B4
    6000,  # 12 F5
    6000,  # 13 B5
    4100,  # 14 F7
    6000,  # 15 F8
    70,  # 16 GF
    68,  # 17 GH
    51,  # 18 GV
    75,  # 19 GN
    69,  # 20 G1
    62,  # 21 G2
    53,  # 22 G3
    55,  # 23 G4
    83,  # 24 LO
    100,  # 25 FT
    0,  # 26 BF
    80,  # 27 LX
    10,  # 28 QU
    20,  # 29 HR
    22,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
)

voice_dennis: Final[tuple[int, ...]] = (
    1,  #  0 SEX
    100,  #  1 SM
    100,  #  2 AS
    110,  #  3 AP
    135,  #  4 PR
    38,  #  5 BR
    0,  #  6 RI
    10,  #  7 NF
    0,  #  8 LA
    105,  #  9 HS
    3200,  # 10 F4
    240,  # 11 B4
    3600,  # 12 F5
    280,  # 13 B5
    4100,  # 14 F7
    6000,  # 15 F8
    68,  # 16 GF
    68,  # 17 GH
    63,  # 18 GV
    76,  # 19 GN
    75,  # 20 G1
    60,  # 21 G2
    52,  # 22 G3
    61,  # 23 G4
    84,  # 24 LO
    100,  # 25 FT
    9,  # 26 BF
    70,  # 27 LX
    50,  # 28 QU
    20,  # 29 HR
    22,  # 30 SR
    0,  # 31 GS
    0,  # 32 OS
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

    The C ``SPDEF`` struct is 39 ints. The ``p_us_vdf_dectalk43.c``
    per-voice initialiser fills 38 slots; this module truncates each row
    to the 33-field convention used throughout the Python pipeline
    (indices 0..30 = ``SEX``..``SR``, index 31 = glottal speed / ``AGO``,
    index 32 = output gain multiplier). The dectalk43 output-gain slot
    (C index 37) and the intervening ``avg_glot_*`` / ``area_chink`` /
    ``open_quo`` slots are all zero, so the truncated index 32 carries
    the (zero) output gain and the remaining ``Spdefs`` fields stay at
    their zero defaults. The Python ``Spdefs`` dataclass matches the C
    field order exactly, so the mapping is positional.

    Args:
        row: A 33-int (or shorter) tuple from one of the
            ``voice_<name>`` constants in this module.

    Returns:
        An :class:`Spdefs` instance with the first ``len(row)`` fields
        populated from ``row`` and the remainder left at their zero
        defaults.
    """
    # ``output_gain_mult`` is carried at index 32 of the truncated row
    # (zero for every dectalk43 voice); the zero-defaulted tail
    # (avg_glot_voicd_open .. junk1) is unchanged from the dataclass
    # default.
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
