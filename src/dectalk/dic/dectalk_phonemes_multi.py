"""Per-language DECtalk-phonemic to ARPABET converters.

Each DECtalk language uses a different phonemic ASCII alphabet — the
character ``T`` is /θ/ in Spanish but /tʰ/ never appears as `T` in US
English; the character `0xe9` (é) marks French acute-e but doesn't
exist in the US alphabet at all. The per-language tables here mirror
the C source files ``src/dapi/src/include/{usa,uk,fr,ger,spa,la}_phon.tab``
and produce ARPABET tokens, mapping non-English phonemes to the
nearest English equivalent when no exact ARPABET symbol exists.

This is a pragmatic approximation: speech quality for non-English
languages will be lower than the original DECtalk output because the
Klatt phoneme→formant table in :mod:`dectalk.ph.phoneme_frames` is
calibrated for English. A future phase can add language-specific
formant tables for proper multi-language quality.
"""

from __future__ import annotations

from typing import Final

from dectalk.dic.dectalk_phonemes import US_MAP as _US_MAP
from dectalk.dic.dectalk_phonemes import is_vowel

# Spanish (Castilian) phoneme map. Most chars match the US table; the
# distinctive Spanish ones below override or add. Source: spa_phon.tab.
_SP_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {
    "T": ("TH",),  # theta - Castilian /θ/ (e.g. zapato, cinco)
    "N": ("N", "Y"),  # palatal nasal /ɲ/ (ñ) - approximated as N + Y
    "L": ("L", "Y"),  # palatal lateral /ʎ/ (ll) - approximated as L + Y
    "R": ("R",),  # trilled R - approximated as plain R
    "C": ("CH",),  # /tʃ/ ch
    "j": ("HH",),  # Spanish j is /x/ ≈ HH
    "B": ("B",),  # voiced bilabial approximant - approximated as B
    "D": ("D",),  # voiced dental approximant - approximated as D
    "G": ("G",),  # voiced velar approximant - approximated as G
    "y": ("Y",),  # palatal glide
    "-": (),  # Spanish syllable separator - silent
}

# Latin American Spanish: drops Castilian /θ/, otherwise same as Spanish.
_LA_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {
    **_SP_OVERRIDES,
    "T": ("S",),  # seseo: /θ/ becomes /s/
}

# French phoneme map. French uses high-bit Latin-1 chars for accented
# vowels and adds nasal vowels. Source: fr_phon.tab.
_FR_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {
    "a": ("AA",),
    "à": ("AA",),  # à
    "é": ("EY",),  # é
    "è": ("EH",),  # è
    "ê": ("EH",),  # ê
    "ë": ("EH",),  # ë
    "e": ("AH",),  # French e is often a schwa
    "i": ("IY",),
    "í": ("IY",),  # í
    "ì": ("IH",),  # ì
    "î": ("IY",),  # î
    "ï": ("IY",),  # ï
    "o": ("OW",),
    "ô": ("OW",),  # ô
    "u": ("UW",),  # French u is /y/ — closest ARPABET is UW
    "y": ("IY",),  # French y as vowel
    "â": ("AA",),  # â (also nasal-a precursor)
    "ä": ("AE",),  # ä
    # Nasal vowels approximated to vowel + nasal (ARPABET has no nasal-vowel symbols)
    "ã": ("AA", "N"),  # ã - nasal a
    "å": ("AA", "N"),  # å (used in fr_phon as nasal a variant)
    "æ": ("EH", "N"),  # æ - nasal e
    # Consonants
    "h": (),  # h is silent in French
    "j": ("ZH",),  # /ʒ/ as in "joue"
    "w": ("W",),
    "r": ("R",),  # uvular /ʁ/ approximated as R
    "f": ("F",), "v": ("V",), "s": ("S",), "z": ("Z",),
    "p": ("P",), "b": ("B",), "t": ("T",), "d": ("D",),
    "k": ("K",), "g": ("G",), "m": ("M",), "n": ("N",),
    "l": ("L",), "x": ("AH",),
    "ç": ("S",),  # ç
}  # fmt: skip

# German phoneme map. Source: ger_phon.tab.
_DE_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {
    # German has front rounded vowels /y ø/ and the ich/ach fricatives.
    # Approximations:
    "X": ("HH",),  # /x/ (Bach) ≈ HH
    "H": ("HH",),  # /ç/ (ich) ≈ HH
    "1": ("L",),  # syllabic l (in fr/ger/sp tables, '1' tends to be syllabic)
    "2": ("N",),  # syllabic n
    "5": ("AH",),  # ə (German schwa)
    "B": ("ER",),  # /ɐ/ (final unstressed -er) ≈ ER
    "T": ("T", "S"),  # /ts/ (z in German)
    # German vowels
    "a": ("AA",), "e": ("EY",), "i": ("IY",), "o": ("OW",), "u": ("UW",),
    "A": ("AY",), "E": ("EH",), "I": ("IH",), "O": ("OY",), "U": ("UH",),
    # Front rounded
    "Y": ("UW",),  # /y/ ≈ UW
    "9": ("ER",),  # /œ/ ≈ ER
    "c": ("AO",),
    # Common consonants
    "p": ("P",), "b": ("B",), "t": ("T",), "d": ("D",),
    "k": ("K",), "g": ("G",), "f": ("F",), "v": ("V",),
    "s": ("S",), "z": ("Z",), "S": ("SH",), "Z": ("ZH",),
    "C": ("CH",), "J": ("JH",), "h": ("HH",),
    "m": ("M",), "n": ("N",), "l": ("L",), "r": ("R",),
    "w": ("W",), "y": ("Y",), "j": ("Y",), "G": ("NG",),
}  # fmt: skip

# UK English uses the US table almost verbatim; differences are in the
# dictionary entries themselves, not the phoneme alphabet.
_UK_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {}


_LANGUAGE_TABLES: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    "us": _US_MAP,
    "uk": {**_US_MAP, **_UK_OVERRIDES},
    "sp": {**_US_MAP, **_SP_OVERRIDES},
    "la": {**_US_MAP, **_LA_OVERRIDES},
    "fr": {**_US_MAP, **_FR_OVERRIDES},
    "de": {**_US_MAP, **_DE_OVERRIDES},
}


def decode_lang(dectalk_phonemic: str, lang: str = "us") -> list[str]:
    """Convert a DECtalk phonemic string to ARPABET using per-language rules.

    Mirrors :func:`dectalk.dic.dectalk_phonemes.decode` but consults the
    language-specific phoneme table.

    Args:
        dectalk_phonemic: Pronunciation string in DECtalk's notation.
        lang: Language tag (``"us"``, ``"uk"``, ``"sp"``, ``"la"``,
            ``"fr"``, ``"de"``).

    Returns:
        ARPABET phoneme list with vowels carrying CMUDict-style stress
        digits.

    Raises:
        ValueError: If ``lang`` is not a recognised language tag.
    """
    if lang not in _LANGUAGE_TABLES:
        raise ValueError(f"unknown lang {lang!r}; supported: {sorted(_LANGUAGE_TABLES)}")

    table = _LANGUAGE_TABLES[lang]
    pending_stress = "0"
    out: list[str] = []
    for ch in dectalk_phonemic:
        if ch == "'":
            pending_stress = "1"
            continue
        if ch == "`":
            pending_stress = "2"
            continue
        mapped = table.get(ch)
        if mapped is None:
            continue
        for tok in mapped:
            if is_vowel(tok):
                out.append(tok + pending_stress)
                pending_stress = "0"
            else:
                out.append(tok)
    return out


def decode_lang_with_markers(dectalk_phonemic: str, lang: str = "us") -> list[str]:
    """Like :func:`decode_lang` but preserves the compound-boundary ``*`` marker.

    The DECtalk dictionary encodes closed compounds (``breakfast``,
    ``pipeline``, ``database``) with an internal ``*`` between the two
    components -- the C LTS turns this into an ``MBOUND`` (``*``) phoneme
    that downstream stages use for stress/timing. The plain decoder
    silently drops ``*``; this variant emits ``"__PUNCT__*"`` so callers
    re-encoding via :func:`dectalk.dic.dectalk_phonemes.encode_to_dectalk`
    get a byte-identical compound emission to the C source.

    Args:
        dectalk_phonemic: Pronunciation string in DECtalk's notation.
        lang: Language tag (``"us"``, ``"uk"``, ``"sp"``, ``"la"``,
            ``"fr"``, ``"de"``).

    Returns:
        ARPABET phoneme list with vowels carrying CMUDict-style stress
        digits, plus ``"__PUNCT__*"`` tokens at compound boundaries.

    Raises:
        ValueError: If ``lang`` is not a recognised language tag.
    """
    if lang not in _LANGUAGE_TABLES:
        raise ValueError(f"unknown lang {lang!r}; supported: {sorted(_LANGUAGE_TABLES)}")

    table = _LANGUAGE_TABLES[lang]
    pending_stress = "0"
    out: list[str] = []
    for ch in dectalk_phonemic:
        if ch == "'":
            pending_stress = "1"
            continue
        if ch == "`":
            pending_stress = "2"
            continue
        if ch == "*":
            out.append("__PUNCT__*")
            continue
        mapped = table.get(ch)
        if mapped is None:
            continue
        for tok in mapped:
            if is_vowel(tok):
                out.append(tok + pending_stress)
                pending_stress = "0"
            else:
                out.append(tok)
    return out
