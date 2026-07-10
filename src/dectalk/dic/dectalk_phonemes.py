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
    # Schwa quality. The C oracle (usa_phon.tab usa_ascky[]) distinguishes
    # three reduced/centralised vowels:
    #   ``^`` -> US_AH (stressed wedge, "but")          — handled above.
    #   ``x`` -> US_AX (unstressed mid-central schwa)   — sofa, banana.
    #   ``|`` -> US_IX (unstressed high-front schwa)    — roses, hospital.
    # Before issue #133 all three were collapsed to ARPABET AH, losing
    # the IX/AX/AH alternation on every multisyllabic word. The
    # mapping below mirrors the C source's usa_ascky_rev[] for ASCII
    # bytes 'x' (120 -> US_AX) and '|' (124 -> US_IX). Uppercase ``X``
    # has NULL_ASCKY in the C table (no DECtalk lexicon uses it); we
    # retain it as an alias for ``x`` so any callers that previously
    # relied on the (incorrect) ``X -> AH`` mapping still resolve to
    # the schwa family rather than crash.
    "x": ("AX",),  # schwa (US_AX, ascky byte 'x')
    "X": ("AX",),  # alias for x — kept for backward compatibility
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
    # ``|`` is US_IX in the C table (usa_ascky[18]). It is the
    # high-front-centralised schwa heard in "roses", "hospital", "civil".
    # Previously collapsed to AH; restored as IX per issue #133.
    "|": ("IX",),  # high schwa marker (US_IX)
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
    {"AA", "AE", "AH", "AO", "AX", "EH", "ER", "IH", "IX", "IY", "UH", "UW",
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
    # The ``yu`` diphthong (usa_arpa[16]). The encoder synthesises it
    # from Y+UW in word-internal position (see the collapse rule in
    # ``encode_to_dectalk``); accepting it as an explicit input symbol
    # lets word-phoneme overrides use it word-finally, where the
    # collapse rule deliberately keeps Y+UW apart (standalone letter
    # ``q`` reads ``k ' yu`` -- issue #244).
    "YU": "yu",
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
        # Pre-rendered raw segment -- the numeric-format expansion
        # (``lts.numeric_formats``) already stringified its phoneme
        # codes through ``usa_arpa`` exactly like the C oracle, so the
        # payload passes through byte-for-byte.
        if tok.startswith("__RAW__"):
            out_parts.append(tok[len("__RAW__") :])
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

            # The IX context for AH0+S word-final fires when the
            # immediately preceding emitted phoneme is a sonorant
            # (L / N / R / a vowel) -- ``dennis`` (N+AH0+S), ``jealous``
            # (L+AH0+S), ``biggest`` (G+AH0+S+T -- where the G is
            # preceded by a vowel). It does NOT fire after M, V, F or
            # other obstruents (``famous`` / ``nervous`` stay AX).
            ah_before_final_s_prev_emit: str = ""
            ah_before_final_s_prev2_emit: str = ""
            if out_parts:
                k_pe = len(out_parts) - 1
                while k_pe >= 0 and out_parts[k_pe] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k_pe -= 1
                if k_pe >= 0:
                    ah_before_final_s_prev_emit = out_parts[k_pe].rstrip(" ")
                k_pe2 = k_pe - 1
                while k_pe2 >= 0 and out_parts[k_pe2] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k_pe2 -= 1
                if k_pe2 >= 0:
                    ah_before_final_s_prev2_emit = out_parts[k_pe2].rstrip(" ")
            # ``M`` is treated as a sonorant for the IX-trigger only
            # when it's itself preceded by another consonant (a cluster
            # context like ``christmas`` -> SM+AH0+S). After a vowel
            # the AH0 stays AX (``famous`` -> EY+M+AH0+S).
            m_in_cluster = (
                ah_before_final_s_prev_emit == "m"
                and ah_before_final_s_prev2_emit
                and ah_before_final_s_prev2_emit not in _VOWEL_DECTALK_CODES
            )
            prev_is_sonorant = (
                ah_before_final_s_prev_emit
                in (
                    "ll",
                    "n",
                    "r",
                    "ng",
                    "nx",
                    "el",
                    "en",
                    "em",
                    # Sibilants / palatal fricatives also trigger
                    # AH0+S -> IX (``conscious`` -> ``aan shixs``,
                    # ``precious`` -> ``ehshixs``).
                    "sh",
                    "zh",
                    "ch",
                    "jh",
                )
                or ah_before_final_s_prev_emit in _VOWEL_DECTALK_CODES
                or m_in_cluster
            )
            ah_before_final_st = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "S"
                and i + 2 < len(phonemes)
                and phonemes[i + 2].rstrip("0123456789") == "T"
                and _word_break_at(i + 3)
            )

            # Multi-syllabic AH0 + word-final K reads as IX (the
            # standard ``-ic`` suffix: ``music`` -> ``m ' yuz ixk``,
            # ``classic`` -> ``k ll' aes ixk``).
            ah_before_final_k = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "K"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
            )
            # Multi-syllabic AH0 + word-final D reads as IX (the ``-id``
            # ending: ``method`` -> ``m ' ehthixd``, ``solid`` -> ``s
            # ' aallixd``). Exceptions:
            # - AX after R or L cluster (``hundred axd``, ``salad axd``)
            # - AX after a vowel (``period iyaxd`` -- the AH0 is right
            #   after IY, no consonant between -- keeps AX schwa)
            # Also fires for AH0+D+Z word-final (the plural ``methods``
            # -> ``m ' ehthixd z``).
            d_then_word_end = _word_break_at(i + 2) or (
                i + 2 < len(phonemes)
                and phonemes[i + 2].rstrip("0123456789") == "Z"
                and _word_break_at(i + 3)
            )
            ah_before_final_d = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "D"
                and d_then_word_end
                and _word_is_multi_syllabic(i)
                and ah_before_final_s_prev_emit not in ("r", "ll", "ir", "ar", "or", "ur", "rr")
                and ah_before_final_s_prev_emit not in _VOWEL_DECTALK_CODES
            )

            # ``-it`` morphological pattern (``visit``, ``limit``, ``edit``):
            # multi-syllabic AH0 + word-final T -> IX + T. Only fires when
            # the stressed vowel in the same word is a short monophthong
            # (IH / EH / AE / AH / AO / UH); diphthong-stressed words
            # like ``private`` (AY) / ``climate`` (AY) keep AX.
            def _stressed_short_vowel_in_word(idx: int) -> bool:
                # Tense monophthongs IY / UW are included alongside the
                # lax monophthongs because the C source treats them the
                # same way for the -it AH0->IX rule.
                short_vowels = {"AE", "AH", "AO", "EH", "IH", "UH", "IY", "UW"}
                for j in range(idx - 1, -1, -1):
                    ph_j = phonemes[j]
                    if not ph_j or ph_j == "_" or ph_j.startswith("__"):
                        break
                    if ph_j and ph_j[-1].isdigit() and ph_j[-1] in "12":
                        return ph_j[:-1] in short_vowels
                for j in range(idx + 1, len(phonemes)):
                    ph_j = phonemes[j]
                    if not ph_j or ph_j == "_" or ph_j.startswith("__"):
                        break
                    if ph_j and ph_j[-1].isdigit() and ph_j[-1] in "12":
                        return ph_j[:-1] in short_vowels
                return False

            ah_before_final_t = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "T"
                and _word_break_at(i + 2)
                and _has_prior_vowel_in_word(i)
                and _stressed_short_vowel_in_word(i)
            )
            # Multi-syllabic AH0 + word-final Z reads as IX -- the C
            # source treats this position as the inflected-form schwa
            # (``fixes`` -> ``f ' ihk s ixz``; ``always`` -> ``` aow ixz``).
            # Monosyllabic ``was`` (W AH0 Z) keeps AX.
            ah_before_final_z = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "Z"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
            )
            ah_before_final_s = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "S"
                and _word_break_at(i + 2)
                and _has_prior_vowel_in_word(i)
                and prev_is_sonorant
            ) or ah_before_final_st
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
            # The AH0+N rule has two firing paths:
            # - AH0 + N + T word-final (silent / distant / patient /
            #   parent): fires regardless of preceding consonant -- the
            #   ``-ent`` suffix is reliably reduced.
            # - AH0 + N word-final (no T after): fires only after
            #   sonorants / sibilants. ``cotton`` (T+AH0+N) stays AX;
            #   ``children`` (R+AH0+N) becomes IX.
            n_t_word_final = (
                i + 1 < len(phonemes)
                and phonemes[i + 1].rstrip("0123456789") == "N"
                and i + 2 < len(phonemes)
                and phonemes[i + 2].rstrip("0123456789") == "T"
                and _word_break_at(i + 3)
            )
            n_alone_word_final = (
                i + 1 < len(phonemes)
                and phonemes[i + 1].rstrip("0123456789") == "N"
                and _word_break_at(i + 2)
            )
            # The AH0+N+T rule isn't fully derivable from immediate
            # context -- C treats ``distant`` / ``constant`` / ``talent``
            # / ``vacant`` as IX, but ``instant`` / ``infant`` /
            # ``vibrant`` / ``document`` as AX. The dictionary's
            # form-class flag distinguishes these. We approximate by
            # firing IX only when the preceding emit is a sonorant or
            # sibilant (matching parent/silent/patient/distant); plain
            # stops/fricatives without that prefix stay AX.
            # n_t_word_final fires for ``-ent``/``-ant`` after sonorant/
            # sibilant prev (distant, silent, patient, parent, constant,
            # talent). T also passes via this path for ``distant`` /
            # ``constant`` but it would over-fire for ``instant`` /
            # ``infant`` -- those go to AX. We accept the gap because
            # the dictionary's form-class flag isn't derivable from
            # immediate context. n_alone_word_final uses the narrower
            # set (no T) so ``cotton`` stays AX.
            # ``parent`` (P EY1 R AH0 N T) emits ``p ' eyr ixn t`` --
            # the prev_emit is ``r`` (the R after a vowel) and AH0+N+T
            # fires IX. ``different`` (D IH1 F R AH0 N T) also emits
            # prev_emit ``r``, but the R follows the consonant ``f``
            # rather than a vowel, and AH0+N+T stays AX. Distinguish
            # by inspecting prev2_emit: vowel-before-R reads as IX,
            # consonant-before-R reads as AX.
            prev2_emit_base: str = ""
            if out_parts:
                k2 = len(out_parts) - 1
                # Skip the immediate prev emit + any stress markers.
                while k2 >= 0 and out_parts[k2] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k2 -= 1
                k2 -= 1  # step past prev_emit_base itself
                while k2 >= 0 and out_parts[k2] in (
                    f"{DECTALK_PRIMARY_STRESS} ",
                    f"{DECTALK_SECONDARY_STRESS} ",
                ):
                    k2 -= 1
                if k2 >= 0:
                    prev2_emit_base = out_parts[k2].rstrip(" ")
            prev_is_vowel_plus_r = prev_emit_base == "r" and prev2_emit_base in _VOWEL_DECTALK_CODES
            ah_before_final_n = (
                base == "AH"
                and stress_digit == "0"
                and (
                    (
                        n_t_word_final
                        and (
                            prev_emit_base
                            in ("sh", "zh", "ch", "jh", "b", "z", "s", "ll", "t", "k")
                            or prev_is_vowel_plus_r
                        )
                    )
                    or (
                        n_alone_word_final
                        and (
                            prev_emit_base in ("sh", "zh", "ch", "jh", "b", "z", "s")
                            or prev_is_vowel_plus_r
                        )
                    )
                )
            )
            # AH0 + F + L word-final reads as IX + F + EL (the ``-iful``
            # connector in ``beautiful``).
            ah_before_ful = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "F"
                and i + 2 < len(phonemes)
                and phonemes[i + 2].rstrip("0123456789") == "L"
                and (
                    i + 3 >= len(phonemes)
                    or phonemes[i + 3] == "_"
                    or (phonemes[i + 3] or "").startswith("__")
                )
            )
            # AH0 + word-final V (multi-syllabic) reads as IX (the
            # ``-ive`` suffix: ``active`` -> ``' aek t ixv``, ``native``
            # -> ``n ' eyt ixv``).
            ah_before_final_v = (
                base == "AH"
                and stress_digit == "0"
                and next_base == "V"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
            )
            # AH0 + word-final SH (multi-syllabic) reads as IX (the
            # ``-ish`` suffix: ``finish`` -> ``f ' ihn ixsh``).
            ah_before_final_sh = (
                base in ("AH", "IH")
                and stress_digit == "0"
                and next_base == "SH"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
            )
            # AH0 + word-final P after coronal-sonorant prev emit reads
            # as IX (``syrup`` / ``gossip`` / ``turnip`` / ``tulip``).
            # After L (``gallop`` / ``develop``) stays AX -- gated out
            # because the C source's rule depends on the L's syllable
            # boundary which we can't easily detect here.
            ah_before_final_p = (
                base in ("AH", "IH")
                and stress_digit == "0"
                and next_base == "P"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
                and ah_before_final_s_prev_emit in ("r", "s", "n", "t")
            )
            # AH0 + word-final F after coronal-sonorant prev emit reads
            # as IX (``sheriff`` / ``mastiff`` / ``midriff``).
            # Also fires when the F is followed by a single STRESSED
            # vowel + word-end -- the ``-fy`` verb suffix in words
            # like ``justify`` (lex ``JH AH1 S T AH0 F AY2``: AY has
            # secondary stress, AH0 -> IX). ``notify`` / ``verify``
            # have lex AY0 (no stress) and stay AX.
            _next_after_f = phonemes[i + 2] if i + 2 < len(phonemes) else ""
            _next_after_f_base = _next_after_f.rstrip("0123456789")
            _next_after_f_stress = (
                _next_after_f[-1] if _next_after_f and _next_after_f[-1].isdigit() else ""
            )
            ah_before_f_then_fy_suffix = (
                base in ("AH", "IH")
                and stress_digit == "0"
                and next_base == "F"
                and _next_after_f_base == "AY"
                and _next_after_f_stress in ("1", "2")
                and _word_break_at(i + 3)
                and _word_is_multi_syllabic(i)
                and ah_before_final_s_prev_emit in ("r", "s", "n", "t", "ll")
            )
            ah_before_final_f = (
                base in ("AH", "IH")
                and stress_digit == "0"
                and next_base == "F"
                and _word_break_at(i + 2)
                and _word_is_multi_syllabic(i)
                and ah_before_final_s_prev_emit in ("r", "s", "n", "t", "ll")
            ) or ah_before_f_then_fy_suffix
            # AH0/IH0 + S + F + AY at word-end reads as IX (the
            # ``-sify`` suffix in ``satisfy`` -> ``s ' aet ixs f ay``).
            # Mirrors ``ah_before_f_then_fy_suffix`` but with an extra
            # S between the reduced vowel and the F. The C source
            # accepts AY0 here (lex ``S AE1 T AH0 S F AY0``) so we do
            # not gate on stress digit.
            _ph_i2 = phonemes[i + 2] if i + 2 < len(phonemes) else ""
            _ph_i2_base = _ph_i2.rstrip("0123456789")
            _ph_i3 = phonemes[i + 3] if i + 3 < len(phonemes) else ""
            _ph_i3_base = _ph_i3.rstrip("0123456789")
            ah_before_s_then_fy_suffix = (
                base in ("AH", "IH")
                and stress_digit == "0"
                and next_base == "S"
                and _ph_i2_base == "F"
                and _ph_i3_base == "AY"
                and _word_break_at(i + 4)
                and _word_is_multi_syllabic(i)
                and ah_before_final_s_prev_emit in ("r", "s", "n", "t", "ll")
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
            # The sonorant is "word-final enough" for the syllabic
            # rule when followed by a word break OR when followed by
            # ``T`` that is itself word-final (``didn't`` -> ``D EN T``,
            # ``couldn't`` -> ``D EN T`` -- the contraction's -n't).
            next_is_word_end = (
                i + 1 >= len(phonemes)
                or phonemes[i + 1] == "_"
                or not phonemes[i + 1]
                or (phonemes[i + 1] or "").startswith("__")
            )
            t_then_word_end = (
                i + 1 < len(phonemes)
                and phonemes[i + 1].rstrip("0123456789") in ("T", "D")
                and (
                    i + 2 >= len(phonemes)
                    or phonemes[i + 2] == "_"
                    or not phonemes[i + 2]
                    or (phonemes[i + 2] or "").startswith("__")
                )
            )
            if (
                base in ("L", "N")
                and not stress_digit
                and (next_is_word_end or t_then_word_end)
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
                if (
                    ah_before_final_s
                    or next_base == "NG"
                    or ah_before_final_n
                    or ah_before_ful
                    or ah_before_final_t
                    or ah_before_final_z
                    or ah_before_final_k
                    or ah_before_final_d
                    or ah_before_final_v
                    or ah_before_final_sh
                    or ah_before_final_p
                    or ah_before_final_f
                    or ah_before_s_then_fy_suffix
                ):
                    dt = "ix"
                elif _word_is_multi_syllabic(i) or next_is_fricative or next_is_word_end:
                    dt = "ax"
                else:
                    dt = "ah"
            elif (
                base == "IH"
                and stress_digit == "0"
                and (
                    next_base == "NG"
                    or (next_base == "K" and _word_break_at(i + 2) and _word_is_multi_syllabic(i))
                    or ah_before_final_sh
                    or ah_before_final_p
                    or ah_before_final_f
                    or ah_before_s_then_fy_suffix
                )
            ):
                dt = "ix"
            elif syllabic_after_consonant_word_final and base == "L":
                dt = "el"
            elif syllabic_after_consonant_word_final and base == "N":
                dt = "en"
            # N -> NG before K / G (velar assimilation): ``pink`` ->
            # ``p ' ihnxk``, ``bank`` -> ``b ' aenxk``.
            elif base == "N" and not stress_digit and next_base in ("K", "G"):
                dt = "nx"
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
