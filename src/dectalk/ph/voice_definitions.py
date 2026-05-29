"""US English voice-definition tables.

Translated from ``src/dapi/src/ph/p_us_vdf_dectalk43.c`` — the active
DECtalk 4.3 voice-definition file. ``dectalkf.h`` includes
``dectalkf_klsyn.h``, which leaves ``HLSYN`` undefined and selects
``VDF_DECTALK_43`` (``dectalkf_klsyn.h:280``); ``ph_vdefi.c`` then
``#include``-s ``p_us_vdf_dectalk43.c``. At the default 11025 Hz sample
rate, ``ph_vset.c:449-459`` loads the **non-``_8``** rows
(``voidef[voice]`` = ``paul``/``betty``/…) rather than the 8 kHz
``_8`` variants (selected only below 8763 Hz). These are the rows the
C oracle binary actually synthesises from, so the Python literals below
mirror them byte-for-byte.

Each entry is the ``SPDEF`` voice array, indexed by the ``SPD_*``
constants in ``cmd.h``:

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
 14  F7 parallel 4th formant freq (SPD_P4)
 15  F8 parallel 5th formant freq (SPD_P5)
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
 31  AGO average glottal opening (SPD_AGO)
 32  AGVO avg glottal opening for a voiced obstruent
 33  AGUO avg glottal opening for an unvoiced obstruent
 34  UNVOW (SPD_UNVOW)
 35  CHINK chink area (SPD_CHINK)
 36  OQ open quotient (SPD_OQ)
 37  OS output gain multiplier (SPD_OS)

Parsed for the Linux build (``FP_VTM`` / ``HLSYN`` undefined). The C
struct is ``SPDEF`` = 39 ints; the ``p_us_vdf_dectalk43.c`` initialisers
fill the first 38 (slot 38 is ``SPD_NM`` — the speaker number — written
at load time by ``ph_vset.c``). Unlike the older ``p_us_vdf.c`` rows
(33 ints, ``GS`` at 31 and an ``#ifndef FP_VTM`` output-gain at 32), the
4.3 rows zero out the whole AGO..OS tail.
"""

from __future__ import annotations

from typing import Final

from dectalk.api.spdefs_struct import Spdefs

voice_paul: Final[tuple[int, ...]] = (
    1, 3, 100, 122, 100, 0, 70, 0, 0, 100,  # SEX SM AS AP PR BR RI NF LA HS
    3300, 260, 3650, 330, 3350, 3850,       # F4 B4 F5 B5 F7 F8
    70, 70, 65, 74, 68, 60, 48, 64,         # GF GH GV GN G1 G2 G3 G4
    86, 75, 18, 0, 40, 18, 32,              # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

# Crusty Chris is not a distinct row in the 4.3 voice table — the C
# ``ph_main.c`` voice directory maps every non-canonical slot to ``paul``
# and ``p_us_vdf_dectalk43.c`` ships no ``chris`` array. Alias Paul.
voice_chris: Final[tuple[int, ...]] = voice_paul

voice_betty: Final[tuple[int, ...]] = (
    0, 4, 35, 208, 240, 0, 40, 0, 0, 100,   # SEX SM AS AP PR BR RI NF LA HS
    4450, 260, 6000, 6000, 4100, 6000,      # F4 B4 F5 B5 F7 F8 (F5/B5/F8 = ZAPF/ZAPB)
    72, 70, 65, 72, 69, 65, 50, 56,         # GF GH GV GN G1 G2 G3 G4
    81, 75, 0, 80, 55, 14, 20,              # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_harry: Final[tuple[int, ...]] = (
    1, 12, 100, 89, 80, 0, 86, 10, 0, 115,  # SEX SM AS AP PR BR RI NF LA HS
    3300, 200, 3850, 240, 3200, 4000,       # F4 B4 F5 B5 F7 F8
    70, 70, 65, 73, 71, 60, 52, 62,         # GF GH GV GN G1 G2 G3 G4
    81, 60, 9, 0, 10, 20, 30,               # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_frank: Final[tuple[int, ...]] = (
    1, 46, 65, 155, 90, 50, 40, 0, 5, 90,   # SEX SM AS AP PR BR RI NF LA HS
    3650, 280, 4200, 300, 3500, 4050,       # F4 B4 F5 B5 F7 F8
    68, 68, 63, 75, 63, 58, 56, 66,         # GF GH GV GN G1 G2 G3 G4
    86, 100, 9, 50, 0, 20, 22,              # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_kit: Final[tuple[int, ...]] = (
    0, 5, 65, 306, 210, 47, 40, 0, 0, 80,   # SEX SM AS AP PR BR RI NF LA HS
    6000, 6000, 6000, 6000, 4450, 6000,     # F4 B4 F5 B5 F7 F8 (F4/B4/F5/B5/F8 = ZAPF/ZAPB)
    72, 70, 65, 71, 69, 69, 52, 50,         # GF GH GV GN G1 G2 G3 G4
    73, 75, 0, 75, 50, 20, 22,              # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_ursula: Final[tuple[int, ...]] = (
    0, 60, 100, 240, 135, 0, 100, 10, 0, 95,  # SEX SM AS AP PR BR RI NF LA HS
    4450, 260, 6000, 6000, 4300, 6000,        # F4 B4 F5 B5 F7 F8 (F5/B5/F8 = ZAPF/ZAPB)
    70, 70, 65, 74, 67, 65, 51, 58,           # GF GH GV GN G1 G2 G3 G4
    80, 100, 8, 50, 30, 20, 32,               # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                      # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_rita: Final[tuple[int, ...]] = (
    0, 24, 65, 106, 80, 46, 20, 0, 4, 95,   # SEX SM AS AP PR BR RI NF LA HS
    4000, 250, 6000, 6000, 4100, 6000,      # F4 B4 F5 B5 F7 F8 (F5/B5/F8 = ZAPF/ZAPB)
    72, 70, 65, 73, 69, 72, 48, 54,         # GF GH GV GN G1 G2 G3 G4
    83, 0, 0, 0, 30, 20, 32,                # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                    # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_wendy: Final[tuple[int, ...]] = (
    0, 100, 50, 200, 175, 55, 0, 10, 0, 100,  # SEX SM AS AP PR BR RI NF LA HS
    4500, 400, 6000, 6000, 4100, 6000,        # F4 B4 F5 B5 F7 F8 (F5/B5/F8 = ZAPF/ZAPB)
    70, 68, 51, 75, 69, 62, 53, 55,           # GF GH GV GN G1 G2 G3 G4
    83, 100, 0, 80, 10, 20, 22,               # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                      # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

voice_dennis: Final[tuple[int, ...]] = (
    1, 100, 100, 110, 135, 38, 0, 10, 0, 105,  # SEX SM AS AP PR BR RI NF LA HS
    3200, 240, 3600, 280, 4100, 6000,          # F4 B4 F5 B5 F7 F8 (F8 = ZAPF)
    68, 68, 63, 76, 75, 60, 52, 61,            # GF GH GV GN G1 G2 G3 G4
    84, 100, 9, 70, 50, 20, 22,                # LO FT BF LX QU HR SR
    0, 0, 0, 0, 0, 0, 0,                       # AGO AGVO AGUO UNVOW CHINK OQ OS
)  # fmt: skip

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
# ``"chris"`` aliases ``voice_paul`` (no separate ``chris`` row exists in
# the 4.3 table). Wendy and Willy are *not* one-to-one in the 4.3 table
# (the public API exposes Willy via the breathy preset), so we map the
# public ``"willy"`` name to ``voice_wendy`` -- the only female breathy
# row in the table -- to keep the public preset names round-trippable
# through the Spdefs scaling.
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
    """Convert a raw 38-int voice row into an :class:`Spdefs` dataclass.

    The C ``SPDEF`` array is 39 ints; the per-voice initialiser in
    ``p_us_vdf_dectalk43.c`` fills the first 38 (slot 38, ``SPD_NM``, is
    the speaker number written at load time). The Python ``Spdefs``
    dataclass mirrors the public ``SPDEFS`` struct, so the mapping is
    positional for slots 0..33 and then follows the ``SPD_*`` index
    semantics (``cmd.h``) for the glottal/chink/open-quotient/output-gain
    tail: ``area_chink`` <- ``SPD_CHINK`` (35), ``open_quo`` <-
    ``SPD_OQ`` (36), ``output_gain_mult`` <- ``SPD_OS`` (37). All of
    those are 0 in every 4.3 voice row.

    Args:
        row: A 38-int tuple from one of the ``voice_<name>`` constants
            in this module.

    Returns:
        An :class:`Spdefs` instance populated from ``row``; the trailing
        ``junk`` / ``junk1`` reserved slots keep their zero defaults.
    """
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
        avg_glot_open=row[31],  # SPD_AGO
        avg_glot_voicd_open=row[32],  # SPD_AGVO
        avg_glot_unv_open=row[33],  # SPD_AGUO
        # row[34] is SPD_UNVOW — no distinct Spdefs field. Spdefs.area_chink
        # mirrors SPD_CHINK (35), open_quo mirrors SPD_OQ (36), and the
        # output-gain multiplier is SPD_OS (37).
        area_chink=row[35],
        open_quo=row[36],
        output_gain_mult=row[37],
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
