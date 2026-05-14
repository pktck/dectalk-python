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
    "Y": "yx",  # consonant Y -- usa_arpa[25] in src/dapi/src/include/usa_phon.tab
    "R": "r",
    "L": "ll",
    "HH": "hx",  # hat -- usa_arpa[28]
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


_TWO_CHAR: Final[int] = 2

_VOWEL_DECTALK_CODES: Final[frozenset[str]] = frozenset(
    {"iy", "ih", "ey", "eh", "ae", "aa", "ay", "aw", "ah", "ao",
     "ow", "oy", "uh", "uw", "ax", "rr"}
)  # fmt: skip


def encode_to_dectalk(  # noqa: PLR0912 — branches mirror C output's per-token formatting
    phonemes: list[str], *, word_break: str = "  "
) -> bytes:
    """Encode an ARPABET phoneme list as DECtalk's ASCII phoneme format.

    Faithful port of the C-source emitter in
    ``src/dapi/src/lts/ls_util.c`` around line 1676: for each
    phoneme symbol the emitter writes ``arpabet[idx]`` then
    ``arpabet[idx+1]`` -- exactly two bytes per symbol. 2-character
    DECtalk codes (``hx`` / ``ax`` / ``ll`` / ``rr`` ...) emit
    as-is; 1-character codes (``f`` / ``b`` / ``k`` ...) emit
    with a trailing space; stress marks emit as ``'`` + space or
    `` ` `` + space.

    Args:
        phonemes: ARPABET phonemes, each optionally suffixed with a
            stress digit (``0`` = none, ``1`` = primary, ``2`` =
            secondary, ``3`` = tertiary -- treated as secondary).
            Word boundaries are signalled by ``"_"`` or empty strings.
        word_break: Extra bytes to emit between words. Defaults to a
            single space; combined with the trailing space the
            previous phoneme already carries, this yields the C
            source's ``  `` (double-space) inter-word separator.

    Returns:
        A ``bytes`` value in DECtalk's native ASCII phoneme alphabet.
        Empty input yields ``b""``.
    """
    out_parts: list[str] = []
    skip_next = False
    for i, tok in enumerate(phonemes):
        if skip_next:
            skip_next = False
            continue
        if not tok or tok == "_":
            out_parts.append(word_break)
            continue
        # Punctuation marker -- the calling layer wraps the actual
        # character in ``__PUNCT__<ch>`` so we can route it through
        # the canonical 2-byte-per-symbol emit (char + trailing space).
        if tok.startswith("__PUNCT__"):
            ch = tok[len("__PUNCT__") :]
            if ch:
                out_parts.append(ch + " ")
            continue
        stress_digit = ""
        base = tok
        if tok and tok[-1].isdigit():
            stress_digit = tok[-1]
            base = tok[:-1]
        # Look-ahead at the next ARPABET phoneme so we can collapse
        # Y+UW into ``yu`` and apply context-sensitive vowel reductions.
        next_base: str | None = None
        next_stress: str = ""
        if i + 1 < len(phonemes):
            nxt = phonemes[i + 1]
            if nxt and nxt != "_":
                if nxt[-1].isdigit():
                    next_stress = nxt[-1]
                    next_base = nxt[:-1]
                else:
                    next_base = nxt
        # Y + UW collapses to the DECtalk diphthong ``yu`` (usa_arpa[16])
        # only when there's at least one more PHONEME (not a word
        # break or punctuation marker) after UW in the same word -- the
        # C source's letter-U-pronounced-as-"yoo" context ("use",
        # "USA", "unite"). When Y+UW are word-final ("you" / "human"
        # endings), C keeps them as separate ``yx`` + ``uw``.
        yu_after = False
        if base == "Y" and next_base == "UW" and i + 2 < len(phonemes):
            after = phonemes[i + 2]
            yu_after = bool(after) and after != "_" and not after.startswith("__")
        if yu_after:
            stress_mark_source = next_stress
            skip_next = True
            dt = "yu"
        else:
            stress_mark_source = stress_digit
            if base == "AH" and stress_digit == "0":
                dt = "ax"
            elif base == "IH" and stress_digit == "0" and next_base == "NG":
                dt = "ix"
            else:
                dt = ARPABET_TO_DECTALK.get(base)
        # Emit the stress marker (now that we've decided which source).
        if stress_mark_source == "1":
            out_parts.append(f"{DECTALK_PRIMARY_STRESS} ")
        elif stress_mark_source in ("2", "3"):
            out_parts.append(f"{DECTALK_SECONDARY_STRESS} ")
        if dt is None:
            # Unknown symbol: emit a question mark so callers can spot
            # the gap. The pure-Python pipeline shouldn't emit these
            # once all ARPABET symbols are covered.
            dt = "?"
        # The C emitter always writes 2 bytes per phoneme: single-char
        # codes get padded with a trailing space.
        out_parts.append(dt + " " if len(dt) == 1 else dt)
    return "".join(out_parts).encode("ascii")
