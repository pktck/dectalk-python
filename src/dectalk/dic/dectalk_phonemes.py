r"""DECtalk-phonemic-string -> ARPABET token list converter.

DECtalk dictionary entries store pronunciations using a compact ASCII
phonemic alphabet rather than ARPABET. Each character represents one
phoneme; a few sigils (``'``, `` ` ``, ``#``, ``*``, ``|``, space) mark
stress, syllable boundaries, and inter-letter separators (used in
initialisms where each letter has its own stressed vowel).

This module exposes :func:`decode` which parses a DECtalk phonemic
string and yields the equivalent ARPABET tokens with CMUDict-style
stress digits. Callers can use the result directly with
:func:`dectalk.ph.sequencer.synthesize_phonemes` or store it as a
lexicon entry alongside the bundled mini-lexicon.
"""

from __future__ import annotations

from typing import Final

# Mapping of DECtalk phonemic characters to one or more ARPABET tokens.
# Compiled from `usa_phon.tab` plus inspection of representative entries
# in `Dic_us.txt`. Where DECtalk fuses an r-coloured vowel into a single
# symbol we expand it to two ARPABET phonemes (e.g. AR -> AA R).
US_MAP: Final[dict[str, tuple[str, ...]]] = {
    # ---- Vowels ----
    "i": ("IY",),  # see
    "I": ("IH",),  # bit
    "e": ("EY",),  # bay
    "E": ("EH",),  # bet
    "@": ("AE",),  # cat
    "a": ("AA",),  # father
    "A": ("AY",),  # buy
    "W": ("AW",),  # cow
    "^": ("AH",),  # but
    "o": ("OW",),  # boat
    "O": ("OY",),  # boy / point / joy
    "U": ("UH",),  # book
    "u": ("UW",),  # boot
    "R": ("ER",),  # bird (r-coloured)
    "Y": ("Y", "UW"),  # 'YU' sound — palatal glide + UW (e.g. "use" = Y UW Z)
    "x": ("AH",),  # schwa (we render as AH; the prosody pass shortens unstressed)
    "X": ("AH",),  # alternate schwa form
    "c": ("AO",),  # bought, caught, dog
    # ---- Consonants ----
    "p": ("P",),
    "b": ("B",),
    "t": ("T",),
    "d": ("D",),
    "k": ("K",),
    "g": ("G",),
    "f": ("F",),
    "v": ("V",),
    "s": ("S",),
    "z": ("Z",),
    "h": ("HH",),
    "m": ("M",),
    "n": ("N",),
    "l": ("L",),
    "r": ("R",),
    "w": ("W",),
    "y": ("Y",),
    "T": ("TH",),
    "D": ("DH",),
    "S": ("SH",),
    "Z": ("ZH",),
    "C": ("CH",),
    "J": ("JH",),
    "G": ("NG",),
    "N": ("N",),  # syllabic N — we approximate as N
    "L": ("L",),  # syllabic L — we approximate as L
    # ---- Other phonemes ----
    "|": ("AH",),  # schwa marker; e.g. 'em -> AH M, asterisk -> ... AH S K
    # ---- Markers we silently skip (don't emit a phoneme) ----
    " ": (),  # word break in multi-word entries (we already split on ',')
    "*": (),  # letter-separator in initialisms
    "#": (),  # syllable boundary
    "&": (),  # rare, glottal-related
}


def decode(dectalk_phonemic: str) -> list[str]:
    """Convert a DECtalk phonemic string to ARPABET tokens with stress digits.

    Walks the input one character at a time. Stress markers (``'``
    primary, `` ` `` secondary) attach to the next vowel emitted. The
    rest of the encoded sigils (``*``, ``#``, ``|``, spaces) are
    silently dropped — they affect DECtalk's prosody/segmentation but
    don't change the phoneme sequence.

    Args:
        dectalk_phonemic: Pronunciation string in DECtalk's notation.

    Returns:
        ARPABET phoneme list with vowels carrying ``0``/``1``/``2``
        stress digits in the CMUDict convention. Unknown characters are
        silently skipped.
    """
    pending_stress = "0"  # default = unstressed
    out: list[str] = []
    for ch in dectalk_phonemic:
        if ch == "'":
            pending_stress = "1"
            continue
        if ch == "`":
            pending_stress = "2"
            continue
        mapped = US_MAP.get(ch)
        if mapped is None:
            # Unknown character — skip rather than crash. This matches the
            # spirit of DECtalk's tolerant lexicon parser.
            continue
        for tok in mapped:
            if is_vowel(tok):
                out.append(tok + pending_stress)
                pending_stress = "0"
            else:
                out.append(tok)
    return out


_VOWELS: Final[frozenset[str]] = frozenset(
    {"AA", "AE", "AH", "AO", "AX", "EH", "ER", "IH", "IY", "UH", "UW",
     "AY", "AW", "EY", "OW", "OY"}
)  # fmt: skip


def is_vowel(token: str) -> bool:
    """Return True if ``token`` is an ARPABET vowel/diphthong (no stress digit)."""
    return token in _VOWELS
