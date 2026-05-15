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
    # ---- Centralised / r-coloured vowel codes ----
    # DECtalk has IX (usa_arpa[18]) for centralised unstressed I, and
    # the AR / OR / IR / ER / UR r-coloured codes (usa_arpa[19-23]).
    # We accept them as explicit ARPABET-style symbols so callers can
    # hand-craft phonemes that need them (e.g. word-phoneme overrides
    # for "dalmatians" / digit-expanded "forty").
    "IX": "ix",
    "IR": "ir",
    "AR": "ar",
    "OR": "or",
    "UR": "ur",
    # Syllabic-consonant codes from the C source's eng_ph_table
    # (``samplosf/src/emacspeak/src/phoneme.c`` rows EN / EL / EM).
    # DECtalk's LTS emits these for unstressed-N-after-fricative
    # ("version" -> v rr zh en), unstressed-L-after-stop ("bottle"
    # -> b aa t el), and unstressed-M-after-stop ("rhythm" -> r ih
    # dh em). Used by callers via ``word_phoneme_overrides`` to
    # match the C output's syllabic-consonant pronunciation.
    "EN": "en",
    "EL": "el",
    "EM": "em",
    # Light-L (US_LX) and r-tap (US_RX) allophones from the same
    # eng_ph_table rows. Used in DECtalk's first-verbs table for
    # ``will`` (W IH LX) and elsewhere.
    "LX": "lx",
    "RX": "rx",
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
     "ow", "oy", "uh", "uw", "ax", "rr",
     "ix", "ir", "er", "ar", "or", "ur"}
)  # fmt: skip


def encode_to_dectalk(  # noqa: PLR0912, PLR0915 — branches mirror C output's per-token formatting
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

            # Detect "word-final S/ST after this position": pattern
            # ``AH0 S _``, ``AH0 S T _``, or ``AH0 S <end>`` (Python's
            # transcription of the C-source's IH0 -> IX context for
            # words like ``dennis`` and the ``-est`` superlative).
            # Only fires when AH0 is preceded by another vowel in the
            # same word -- i.e. it's a reduced-schwa context, not the
            # only vowel as in monosyllabic ``us`` (AH0 S).
            def _word_break_at(idx: int) -> bool:
                if idx >= len(phonemes):
                    return True
                ph = phonemes[idx]
                return not ph or ph == "_" or ph.startswith("__")

            def _has_prior_vowel_in_word(idx: int) -> bool:
                # Walk backwards through ``phonemes`` from ``idx - 1`` to
                # the most recent word-break marker; return True if any
                # token along the way is a vowel.
                for j in range(idx - 1, -1, -1):
                    ph_j = phonemes[j]
                    if not ph_j or ph_j == "_" or ph_j.startswith("__"):
                        break
                    base_j = ph_j.rstrip("0123456789")
                    if base_j in {
                        "AA",
                        "AE",
                        "AH",
                        "AO",
                        "AX",
                        "AY",
                        "AW",
                        "EH",
                        "ER",
                        "EY",
                        "IH",
                        "IX",
                        "IY",
                        "OW",
                        "OY",
                        "UH",
                        "UW",
                    }:
                        return True
                return False

            def _word_is_multi_syllabic(idx: int) -> bool:
                # True iff the word containing ``phonemes[idx]`` has at
                # least one vowel besides the one at ``idx``. Walks both
                # directions to the surrounding word-break markers.
                if _has_prior_vowel_in_word(idx):
                    return True
                vowel_set = {
                    "AA",
                    "AE",
                    "AH",
                    "AO",
                    "AX",
                    "AY",
                    "AW",
                    "EH",
                    "ER",
                    "EY",
                    "IH",
                    "IX",
                    "IY",
                    "OW",
                    "OY",
                    "UH",
                    "UW",
                }
                for j in range(idx + 1, len(phonemes)):
                    ph_j = phonemes[j]
                    if not ph_j or ph_j == "_" or ph_j.startswith("__"):
                        break
                    base_j = ph_j.rstrip("0123456789")
                    if j != idx and base_j in vowel_set:
                        return True
                return False

            ah_before_final_s = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "S"
                and (
                    _word_break_at(i + 2)
                    or (
                        i + 2 < len(phonemes)
                        and phonemes[i + 2].rstrip("0123456789") == "T"
                        and _word_break_at(i + 3)
                    )
                )
                and _has_prior_vowel_in_word(i)
            )
            # AH0 + word-final N preceded by a palatal/post-alveolar
            # affricate / fricative (SH / ZH / CH / JH) or R reads as
            # IX (the -tion / -tian / -ren morphology -- ``nation``,
            # ``mission``, ``children``).
            prev_emit_base: str = ""
            if out_parts:
                k = len(out_parts) - 1
                while k >= 0 and out_parts[k] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k -= 1
                if k >= 0:
                    prev_emit_base = out_parts[k].rstrip(" ")
            ah_before_final_n = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "N"
                and (
                    i + 2 >= len(phonemes)
                    or phonemes[i + 2] == "_"
                    or (phonemes[i + 2] or "").startswith("__")
                )
                and prev_emit_base in ("sh", "zh", "ch", "jh", "r")
            )
            # Word-final L / N preceded by a consonant collapses to
            # the syllabic-L / syllabic-N allophone (``el`` / ``en``,
            # US_EL / US_EN). DECtalk applies this whenever there's
            # no vowel between the syllable's last stop/fricative
            # and the sonorant (e.g. "apple" -> AE P L -> aep + el;
            # "button" -> B AH T N -> b ' aht + en). When L/N is
            # preceded by a vowel ("fall" -> F AO L; "rain" -> R EY
            # N) it stays as the plain code.
            syllabic_after_consonant_word_final = False
            if (
                base in ("L", "N")
                and not stress_digit
                and (
                    i + 1 >= len(phonemes)
                    or phonemes[i + 1] == "_"
                    or not phonemes[i + 1]
                    or (phonemes[i + 1] or "").startswith("__")
                )
                and out_parts
            ):
                # Walk back through any stress-marker emit to find
                # the actual previous phoneme code.
                k = len(out_parts) - 1
                while k >= 0 and out_parts[k] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k -= 1
                if k >= 0:
                    prev_emit = out_parts[k].rstrip(" ")
                    if prev_emit and prev_emit not in _VOWEL_DECTALK_CODES:
                        syllabic_after_consonant_word_final = True
            if base == "AH" and stress_digit == "0":
                # Multi-syllable words: AH0 reduces to AX. In
                # monosyllabic function-word context, AH0 before a
                # fricative (S/Z/V/F) still reduces (``of``, ``us``);
                # before a stop or nasal it keeps its full AH quality
                # (``some``, ``but``).
                next_is_fricative = next_base in {"S", "Z", "V", "F"}
                # AH0 is word-final iff there's a word break right after.
                next_is_word_end = (
                    i + 1 >= len(phonemes)
                    or phonemes[i + 1] == "_"
                    or not phonemes[i + 1]
                    or (phonemes[i + 1] or "").startswith("__")
                )
                if ah_before_final_s or next_base == "NG" or ah_before_final_n:
                    dt = "ix"
                elif _word_is_multi_syllabic(i) or next_is_fricative or next_is_word_end:
                    dt = "ax"
                else:
                    dt = "ah"
            elif base == "IH" and stress_digit == "0" and next_base == "NG":
                dt = "ix"
            elif syllabic_after_consonant_word_final and base == "L":
                dt = "el"
            elif syllabic_after_consonant_word_final and base == "N":
                dt = "en"
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
