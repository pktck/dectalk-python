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


# Canonical DECtalk phoneme table, ported from
# ``/tmp/dectalk-src/src/samplosf/src/emacspeak/src/phoneme.c`` (the
# ``eng_ph_table`` array at lines 41-117). Column 1 of the C table is
# DECtalk's single-letter / bracketed internal phoneme code; column 2 is
# the ASCII string emitted by ``TextToSpeechConvertToPhonemes`` (2-letter
# in most cases, single letter for simple consonants); column 3 is an
# example word (informational only).
#
# This table is the canonical mapping the C source uses when it
# stringifies its internal phoneme stream. The Python port consumes it
# to produce DECtalk-native phoneme strings that can be byte-compared
# against ``CAPI.convert_to_phonemes`` output.
ARPABET_TO_DECTALK: Final[dict[str, str]] = {
    # ---- Vowels ----
    "IY": "iy",  # beet
    "IH": "ih",  # bit
    "EY": "ey",  # bait
    "EH": "eh",  # bet
    "AE": "ae",  # bat
    "AA": "aa",  # bob
    "AY": "ay",  # buy
    "AW": "aw",  # bout
    "AH": "ah",  # but
    "AO": "ao",  # bought
    "OW": "ow",  # boat
    "OY": "oy",  # boy
    "UH": "uh",  # put
    "UW": "uw",  # view
    "ER": "rr",  # burr (r-coloured)
    "AX": "ax",  # schwa
    # ---- Consonants ----
    "W": "w",
    "Y": "y",
    "R": "r",
    "L": "ll",
    "HH": "hx",  # hat -- C source emits 'hx' (single 'h' character is internal-only)
    "M": "m",
    "N": "n",
    "NG": "nx",
    "F": "f",
    "V": "v",
    "TH": "th",
    "DH": "dh",
    "S": "s",
    "Z": "z",
    "SH": "sh",
    "ZH": "zh",
    "P": "p",
    "B": "b",
    "T": "t",
    "D": "d",
    "K": "k",
    "G": "g",
    "CH": "ch",
    "JH": "jh",
    "Q": "q",
}


# Stress markers used in DECtalk's ASCII phoneme format. Primary stress
# is ``'``, secondary stress is ``` ` ```; both appear as their own
# space-separated tokens preceding the stressed vowel.
DECTALK_PRIMARY_STRESS: Final[str] = "'"
DECTALK_SECONDARY_STRESS: Final[str] = "`"


def encode_to_dectalk(phonemes: list[str], *, word_break: str = "  ") -> bytes:
    """Encode an ARPABET phoneme list as DECtalk's ASCII phoneme format.

    The output is what ``TextToSpeechConvertToPhonemes`` would emit on
    the C side: each ARPABET symbol is mapped to its 1- or 2-letter
    DECtalk code via :data:`ARPABET_TO_DECTALK`, stress digits become
    space-padded ``'`` / `` ` `` tokens preceding the vowel, and a
    placeholder ``WBOUND`` or ``BLOCK_RULES`` symbol (None / "_") in
    the input separates words with ``word_break``.

    Args:
        phonemes: ARPABET phonemes, each optionally suffixed with a
            stress digit (``0`` = none, ``1`` = primary, ``2`` =
            secondary, ``3`` = tertiary -- treated as secondary).
            Word boundaries are signalled by ``"_"`` or empty strings.
        word_break: Bytes to emit between words. Defaults to two
            spaces (matching the C source's `` `` separator).

    Returns:
        A ``bytes`` value in DECtalk's native ASCII phoneme alphabet.
        Empty input yields ``b""``.
    """
    out_parts: list[str] = []
    for tok in phonemes:
        if not tok or tok == "_":
            out_parts.append(word_break)
            continue
        stress_digit = ""
        base = tok
        if tok and tok[-1].isdigit():
            stress_digit = tok[-1]
            base = tok[:-1]
        # AH0 (unstressed AH) is the schwa in DECtalk's alphabet --
        # emit ``ax`` rather than ``ah``. The stressed AH1 stays ``ah``.
        dt = "ax" if base == "AH" and stress_digit == "0" else ARPABET_TO_DECTALK.get(base)
        if dt is None:
            # Unknown symbol: emit a question mark so callers can spot
            # the gap. The pure-Python pipeline shouldn't emit these
            # once all ARPABET symbols are covered.
            dt = "?"
        if stress_digit == "1":
            out_parts.append(f" {DECTALK_PRIMARY_STRESS} {dt}")
        elif stress_digit in ("2", "3"):
            out_parts.append(f" {DECTALK_SECONDARY_STRESS} {dt}")
        else:
            out_parts.append(dt)
    # Collapse a possible leading space before the first stress marker
    # so the output starts at column 0 -- mirrors the C source which
    # writes ``" ' ey"`` for the standalone word "a" (no leading
    # space).
    encoded = "".join(out_parts)
    if encoded.startswith(" "):
        encoded = encoded[1:]
    # C convention: words ending in a consonant get a trailing space;
    # vowel-final words don't. We approximate by looking at the last
    # ARPABET token that wasn't a word break.
    last_phoneme = None
    for tok in reversed(phonemes):
        if tok and tok != "_":
            last_phoneme = tok
            break
    if last_phoneme is not None:
        base = last_phoneme.rstrip("0123456789")
        if base in ARPABET_TO_DECTALK and base not in _VOWELS:
            encoded = encoded + " "
    return encoded.encode("ascii")
