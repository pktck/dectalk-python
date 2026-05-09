"""Phoneme → Klatt frame parameter mapping.

Builds an :class:`LLFrame` for each ARPABET phoneme using formant
frequencies and bandwidths from Klatt's 1980 reference tables (vowels) and
the standard speech-synthesis literature (consonants). Diphthongs return
two frames (start + end target) so the caller can interpolate.

This is a pragmatic, hand-tuned starting set — the full DECtalk PH module
has thousands of context-sensitive rules. Using a direct phoneme → frame
table gets us an MVP that can pronounce arbitrary phoneme strings; later
phases can refine with proper context-dependent allophonic variation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.include.phonemes import PhonemeKind, get_phoneme

# Default voicing parameters shared across all voiced phonemes. F0 is set
# by the prosody pass; here we just need a non-zero placeholder so the
# voicing source produces output.
_VOICED_F0_DEFAULT: Final[int] = 1220  # 122 Hz times 10
_VOICED_AV: Final[int] = 60
_VOICELESS_AV: Final[int] = 0

# Aspiration / frication amplitudes for voiceless consonants.
_FRICATIVE_AF: Final[int] = 60
_ASPIRATED_AH: Final[int] = 50
_VOICED_FRIC_AV: Final[int] = 50  # voiced fricatives have both voicing and noise

# Higher-formant defaults (F4-F6) used when a phoneme doesn't specify them.
_DEFAULT_F4: Final[int] = 3500
_DEFAULT_B4: Final[int] = 250
_DEFAULT_F5: Final[int] = 4500
_DEFAULT_B5: Final[int] = 300
_DEFAULT_F6: Final[int] = 5500
_DEFAULT_B6: Final[int] = 500


def _vowel_frame(
    *,
    f1: int,
    b1: int,
    f2: int,
    b2: int,
    f3: int,
    b3: int,
    f0_x10: int = _VOICED_F0_DEFAULT,
) -> LLFrame:
    """Build a steady-state vowel frame."""
    return LLFrame(
        F0=f0_x10,
        AV=_VOICED_AV,
        OQ=50,
        SQ=200,
        TL=0,
        F1=f1,
        B1=b1,
        F2=f2,
        B2=b2,
        F3=f3,
        B3=b3,
        F4=_DEFAULT_F4,
        B4=_DEFAULT_B4,
        F5=_DEFAULT_F5,
        B5=_DEFAULT_B5,
        F6=_DEFAULT_F6,
        B6=_DEFAULT_B6,
    )


# ----------------------------------------------------------------- vowels
# Klatt 1980 table 2: adult-male English vowels. F1/F2/F3 in Hz.
_VOWEL_FORMANTS: Final[dict[str, tuple[int, int, int, int, int, int]]] = {
    # code: (F1, B1, F2, B2, F3, B3)
    "AA": (730, 90, 1090, 110, 2440, 170),  # father
    "AE": (660, 100, 1720, 130, 2410, 200),  # cat
    "AH": (640, 80, 1190, 90, 2390, 130),  # but
    "AO": (570, 80, 840, 80, 2410, 170),  # bought
    "AX": (500, 80, 1500, 110, 2500, 170),  # schwa
    "EH": (530, 80, 1840, 110, 2480, 170),  # bet
    "ER": (490, 60, 1350, 80, 1690, 120),  # bird (r-coloured)
    "IH": (390, 70, 1990, 100, 2550, 170),  # bit
    "IY": (270, 60, 2290, 90, 3010, 170),  # see
    "UH": (440, 70, 1020, 90, 2240, 130),  # book
    "UW": (300, 70, 870, 80, 2240, 160),  # boot
}


def _vowel(code: str) -> LLFrame:
    f1, b1, f2, b2, f3, b3 = _VOWEL_FORMANTS[code]
    return _vowel_frame(f1=f1, b1=b1, f2=f2, b2=b2, f3=f3, b3=b3)


# ----------------------------------------------------------- diphthongs
# Each diphthong is a pair (start, end) of vowel frames.
_DIPHTHONG_TARGETS: Final[dict[str, tuple[str, str]]] = {
    "AY": ("AA", "IH"),  # buy: open back -> high front
    "AW": ("AA", "UH"),  # cow: open back -> high back
    "EY": ("EH", "IH"),  # bay: mid front -> high front
    "OW": ("AO", "UH"),  # boat: mid back -> high back
    "OY": ("AO", "IH"),  # boy: mid back -> high front
}


def _diphthong(code: str) -> tuple[LLFrame, LLFrame]:
    a, b = _DIPHTHONG_TARGETS[code]
    return _vowel(a), _vowel(b)


# ------------------------------------------------------------ consonants
# Place-of-articulation cues encoded as locus formant targets that the
# vowel side adapts toward during a CV transition. For the steady portion
# of a consonant, we set lower amplitude / higher bandwidth to suppress
# audible ringing.


# Bilabial stops (P, B, M): low F2 locus, near 700-800 Hz.
# Alveolar stops (T, D, N): mid-high F2 locus, near 1700 Hz.
# Velar stops (K, G, NG): F2 ≈ F3 pinch, around 2300 Hz.
def _stop(*, f1: int, f2: int, f3: int, voiced: bool) -> LLFrame:
    base = _vowel_frame(f1=f1, b1=200, f2=f2, b2=200, f3=f3, b3=300)
    return replace(
        base,
        AV=_VOICED_AV // 2 if voiced else _VOICELESS_AV,
        Ah=_ASPIRATED_AH if not voiced else 0,
    )


def _voiceless_fric(
    *, f1: int, f2: int, f3: int, a2f: int = 60, a3f: int = 60, a4f: int = 60
) -> LLFrame:
    base = _vowel_frame(f1=f1, b1=300, f2=f2, b2=300, f3=f3, b3=300)
    return replace(base, AV=0, Af=_FRICATIVE_AF, A2f=a2f, A3f=a3f, A4f=a4f)


def _voiced_fric(
    *, f1: int, f2: int, f3: int, a2f: int = 50, a3f: int = 50, a4f: int = 50
) -> LLFrame:
    base = _vowel_frame(f1=f1, b1=200, f2=f2, b2=200, f3=f3, b3=200)
    return replace(base, AV=_VOICED_FRIC_AV, Af=_FRICATIVE_AF - 10, A2f=a2f, A3f=a3f, A4f=a4f)


def _nasal(*, f1: int, f2: int, f3: int) -> LLFrame:
    base = _vowel_frame(f1=f1, b1=80, f2=f2, b2=80, f3=f3, b3=120)
    # Boost the nasal pole/zero to give the segment its characteristic muffled
    # quality.
    return replace(base, AV=_VOICED_AV - 10, FNP=270, BNP=100, FNZ=450, BNZ=100)


_CONSONANT_FRAMES: Final[dict[str, LLFrame]] = {
    # Bilabial
    "P": _stop(f1=200, f2=900, f3=2200, voiced=False),
    "B": _stop(f1=200, f2=900, f3=2200, voiced=True),
    "M": _nasal(f1=300, f2=900, f3=2200),
    # Alveolar
    "T": _stop(f1=300, f2=1700, f3=2700, voiced=False),
    "D": _stop(f1=300, f2=1700, f3=2700, voiced=True),
    "N": _nasal(f1=300, f2=1700, f3=2700),
    # Velar
    "K": _stop(f1=300, f2=2200, f3=2400, voiced=False),
    "G": _stop(f1=300, f2=2200, f3=2400, voiced=True),
    "NG": _nasal(f1=300, f2=2200, f3=2400),
    # Fricatives — voiceless
    "F": _voiceless_fric(f1=400, f2=1400, f3=2400, a2f=20, a3f=40, a4f=60),
    "TH": _voiceless_fric(f1=400, f2=1700, f3=2400, a2f=30, a3f=50, a4f=60),
    "S": _voiceless_fric(f1=400, f2=1700, f3=2400, a2f=20, a3f=40, a4f=80),
    "SH": _voiceless_fric(f1=400, f2=1800, f3=2400, a2f=40, a3f=70, a4f=70),
    "HH": _voiceless_fric(f1=500, f2=1500, f3=2500, a2f=40, a3f=50, a4f=50),
    # Fricatives — voiced
    "V": _voiced_fric(f1=350, f2=1400, f3=2400, a2f=20, a3f=40, a4f=50),
    "DH": _voiced_fric(f1=350, f2=1700, f3=2400, a2f=30, a3f=50, a4f=50),
    "Z": _voiced_fric(f1=350, f2=1700, f3=2500, a2f=20, a3f=40, a4f=70),
    "ZH": _voiced_fric(f1=350, f2=1800, f3=2400, a2f=40, a3f=70, a4f=60),
    # Affricates: stop-burst then fricative — modelled as the fricative target.
    "CH": _voiceless_fric(f1=400, f2=1800, f3=2400, a2f=40, a3f=70, a4f=70),
    "JH": _voiced_fric(f1=350, f2=1800, f3=2400, a2f=40, a3f=70, a4f=60),
    # Liquids
    "L": _vowel_frame(f1=350, b1=80, f2=1100, b2=80, f3=2900, b3=120),
    "R": _vowel_frame(f1=400, b1=80, f2=1200, b2=80, f3=1600, b3=120),
    # Glides — basically rapid vowels
    "W": _vowel_frame(f1=300, b1=70, f2=870, b2=80, f3=2240, b3=160),
    "Y": _vowel_frame(f1=270, b1=60, f2=2290, b2=90, f3=3010, b3=170),
}

_SILENCE_FRAME: Final[LLFrame] = replace(LLFrame(), AV=0, Ah=0, Af=0, F0=0)


def get_frames(code: str) -> tuple[LLFrame, ...]:
    """Return the Klatt frame target(s) for a single ARPABET phoneme.

    Vowels and consonants return a single frame; diphthongs return two
    frames (start, end) so the sequencer can interpolate between them.

    Args:
        code: ARPABET symbol, optionally with a trailing stress digit.

    Returns:
        A tuple of :class:`LLFrame`. Length 1 for monophthongs and
        consonants, 2 for diphthongs.

    Raises:
        KeyError: If ``code`` is not in the mapping.
    """
    phoneme = get_phoneme(code)
    if phoneme.kind is PhonemeKind.SILENCE:
        return (_SILENCE_FRAME,)
    if phoneme.kind in {
        PhonemeKind.VOWEL,
    }:
        return (_vowel(phoneme.code),)
    if phoneme.kind is PhonemeKind.DIPHTHONG:
        a, b = _diphthong(phoneme.code)
        return (a, b)
    return (_CONSONANT_FRAMES[phoneme.code],)
