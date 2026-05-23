"""Letter-to-sound rules for US English.

A pragmatic rule-based fallback for words not present in the bundled
lexicon. The full DECtalk LTS module is ~50 C files of context-sensitive
rewrite rules; this Python implementation captures the most productive
English spelling-to-sound patterns in a single ordered rule list.

The matcher is greedy: for each position in the word it tries every rule
in order and applies the first one whose grapheme spelling matches. Each
rule may also constrain the *context* (left and right neighbouring
graphemes) so that, say, ``c`` becomes ``S`` before ``e/i/y`` but ``K``
elsewhere. Word boundaries are denoted by ``^`` (left) and ``$`` (right)
in context patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# A rule is (grapheme, left_pattern_re, right_pattern_re, [phonemes]).
# Empty patterns mean "any context".


@dataclass(frozen=True, slots=True)
class _Rule:
    """One letter-to-sound rule.

    Attributes:
        grapheme: Letters matched at the current position.
        left: Regex matched against the suffix of already-consumed text.
            Empty string means "no constraint".
        right: Regex matched against the remaining text after the
            grapheme. Empty string means "no constraint".
        phones: ARPABET phonemes emitted when the rule fires.
    """

    grapheme: str
    left: str
    right: str
    phones: tuple[str, ...]


# ---------------------------------------------------------------- vowels
# Multi-letter vowel digraphs come first; single letters last.
_VOWEL_RULES: Final[tuple[_Rule, ...]] = (
    _Rule("EAU", "", "", ("Y", "UW")),
    _Rule("EAR", "", "", ("IY", "R")),
    _Rule("AIR", "", "", ("EH", "R")),
    _Rule("OUR", "", "", ("AW", "ER")),
    _Rule("EER", "", "", ("IY", "R")),
    _Rule("OOR", "", "", ("UH", "R")),
    # -OUGH has six different pronunciations in English; sort by
    # increasing generality so the matcher picks the most specific
    # match first.
    #
    # The orthographic suffix -OUGH covers (with the C-oracle ARPABET
    # in parentheses):
    #   bought / thought / sought / ought  -> AO T   (OUGH + T)
    #   though / although                  -> DH OW  (special-cased
    #                                                  via THOUGH and
    #                                                  ALTHOUGH below;
    #                                                  the TH normally
    #                                                  becomes voiceless
    #                                                  but is voiced
    #                                                  here)
    #   through / throughout / throughput  -> TH R UW
    #   bough / plough / slough            -> AW    (OUGH alone, no
    #                                                  trailing letter)
    #   cough / trough                     -> AO F  (OUGH at word end
    #                                                  after C- / TR-)
    #   rough / tough / enough             -> AH F  (default OUGH at
    #                                                  word end; most
    #                                                  common case)
    #
    # Multi-letter forms for the irregular voiced-TH cases ("though",
    # "through") need to consume the leading consonants too — otherwise
    # the default ``TH`` consonant rule fires first and emits a
    # voiceless TH. ``ALTHOUGH`` is included so the leading ``AL`` does
    # not also misfire.
    _Rule("ALTHOUGH", "", "$", ("AO", "L", "DH", "OW")),  # although
    _Rule("THROUGHOUT", "", "$", ("TH", "R", "UW", "AW", "T")),  # throughout
    _Rule("THROUGH", "", "", ("TH", "R", "UW")),  # through, throughput
    _Rule("THOUGH", "", "$", ("DH", "OW")),  # though
    _Rule("OUGH", "", "T", ("AO",)),  # bought, thought, sought, ought
    _Rule("OUGH", "^C", "$", ("AO", "F")),  # cough
    _Rule("OUGH", "TR", "$", ("AO", "F")),  # trough
    # OUGH at end of word with no trailing consonant -> AW
    # (bough, plough, slough). Restricted by left context to B/PL/SL so
    # it doesn't capture rough/tough/enough, which take the AH F rule
    # below.
    _Rule("OUGH", "^B", "$", ("AW",)),  # bough
    _Rule("OUGH", "PL", "$", ("AW",)),  # plough
    _Rule("OUGH", "SL", "$", ("AW",)),  # slough
    _Rule("OUGH", "", "$", ("AH", "F")),  # rough, tough, enough (default)
    _Rule("OUGH", "", "", ("AW",)),  # fallthrough: medial -ough- -> AW
    _Rule("AUGH", "", "T", ("AO",)),  # caught
    _Rule("EIGH", "", "", ("EY",)),  # eight
    _Rule("IGH", "", "", ("AY",)),  # high
    _Rule("AY", "", "", ("EY",)),
    _Rule("AI", "", "", ("EY",)),
    _Rule("AU", "", "", ("AO",)),
    _Rule("AW", "", "", ("AO",)),
    _Rule("EA", "", "", ("IY",)),  # default for "ea"
    _Rule("EE", "", "", ("IY",)),
    _Rule("EI", "", "", ("IY",)),
    _Rule("EY", "", "", ("IY",)),
    _Rule("EU", "", "", ("Y", "UW")),
    _Rule("EW", "", "", ("Y", "UW")),
    _Rule("IE", "", "", ("AY",)),  # tie
    _Rule("OA", "", "", ("OW",)),
    _Rule("OE", "", "", ("OW",)),
    _Rule("OI", "", "", ("OY",)),
    _Rule("OY", "", "", ("OY",)),
    _Rule("OO", "", "", ("UW",)),
    _Rule("OU", "", "", ("AW",)),
    _Rule("OW", "", "", ("OW",)),
    _Rule("UE", "", "", ("UW",)),
    _Rule("UI", "", "", ("UW",)),
    _Rule("UO", "", "", ("UW",)),
    # silent E rules — final E after consonant + vowel pattern is silent.
    _Rule("E", "", "$", ()),  # word-final lone E is often silent
    # Single-vowel + magic-E pattern: VCe -> long vowel
    _Rule("A", "", r"[BCDFGHJKLMNPQRSTVWXZ]E$", ("EY",)),
    _Rule("I", "", r"[BCDFGHJKLMNPQRSTVWXZ]E$", ("AY",)),
    _Rule("O", "", r"[BCDFGHJKLMNPQRSTVWXZ]E$", ("OW",)),
    _Rule("U", "", r"[BCDFGHJKLMNPQRSTVWXZ]E$", ("Y", "UW")),
    # R-coloured single vowels.
    _Rule("AR", "", "", ("AA", "R")),
    _Rule("ER", "", "", ("ER",)),
    _Rule("IR", "", "", ("ER",)),
    _Rule("OR", "", "", ("AO", "R")),
    _Rule("UR", "", "", ("ER",)),
    # Default short vowels.
    _Rule("A", "", "", ("AE",)),
    _Rule("E", "", "", ("EH",)),
    _Rule("I", "", "", ("IH",)),
    _Rule("O", "", "", ("AA",)),
    _Rule("U", "", "", ("AH",)),
    _Rule("Y", "[AEIOU]", "", ()),  # silent after vowel
    _Rule("Y", "", "$", ("IY",)),  # word-final consonantal Y
    _Rule("Y", "", "", ("IH",)),  # default
)


# ------------------------------------------------------------ consonants
_CONSONANT_RULES: Final[tuple[_Rule, ...]] = (
    # Initial-cluster silent-letter rules. English borrows Greek/Latin
    # clusters whose first consonant is silent at word start:
    #
    #   gn-  ->  "n"   (gnaw, gnat, gnome, gnu, gnash, gnostic)
    #   pn-  ->  "n"   (pneumonia, pneumatic)
    #   ps-  ->  "s"   (psychic, psalm, pseudo, psyche)
    #   mn-  ->  "n"   (mnemonic)
    #
    # Each rule consumes a single letter and emits nothing; the following
    # letter is then matched by its normal rule. The empty ``left``
    # pattern anchored at the word start (``^`` becomes ``^$`` after the
    # context matcher's trailing-``$`` append, which matches only when
    # nothing precedes the current position).
    _Rule("G", "^", "N", ()),
    _Rule("P", "^", "N", ()),
    _Rule("P", "^", "S", ()),
    _Rule("M", "^", "N", ()),
    # Multi-letter clusters first.
    _Rule("CH", "", "", ("CH",)),
    _Rule("CK", "", "", ("K",)),
    _Rule("PH", "", "", ("F",)),
    _Rule("SH", "", "", ("SH",)),
    _Rule("TH", "", "", ("TH",)),  # most often voiceless
    _Rule("WH", "", "", ("W",)),
    _Rule("NG", "", "", ("NG",)),
    _Rule("QU", "", "", ("K", "W")),
    _Rule("X", "", "", ("K", "S")),
    _Rule("J", "", "", ("JH",)),
    _Rule("Z", "", "", ("Z",)),
    # C: S before E/I/Y, else K.
    _Rule("C", "", r"[EIY]", ("S",)),
    _Rule("C", "", "", ("K",)),
    # G: JH before E/I/Y at word-final, else G.
    _Rule("G", "", r"[EIY]$", ("JH",)),
    _Rule("G", "", "", ("G",)),
    # S: Z between vowels at end (e.g. dogs -> D AO G Z), else S. Simplified.
    _Rule("S", "[AEIOU]", "$", ("Z",)),
    _Rule("S", "", "", ("S",)),
    # Default singles.
    _Rule("B", "", "", ("B",)),
    _Rule("D", "", "", ("D",)),
    _Rule("F", "", "", ("F",)),
    _Rule("H", "", "", ("HH",)),
    _Rule("K", "", "", ("K",)),
    _Rule("L", "", "", ("L",)),
    _Rule("M", "", "", ("M",)),
    _Rule("N", "", "", ("N",)),
    _Rule("P", "", "", ("P",)),
    _Rule("Q", "", "", ("K",)),
    _Rule("R", "", "", ("R",)),
    _Rule("T", "", "", ("T",)),
    _Rule("V", "", "", ("V",)),
    _Rule("W", "", "", ("W",)),
)

# Concatenated rule list — vowel rules are tried first (since multi-letter
# vowel digraphs need precedence over their first-letter consonant rules,
# but this is fine because consonant rules don't match vowel graphemes).
_RULES: Final[tuple[_Rule, ...]] = _VOWEL_RULES + _CONSONANT_RULES


_VOWEL_PHONEMES: Final[frozenset[str]] = frozenset(
    {"AA", "AE", "AH", "AO", "AX", "EH", "ER", "IH", "IY", "UH", "UW",
     "AY", "AW", "EY", "OW", "OY"}
)  # fmt: skip


# Letters that count as vowels for spelling-side syllable counting. ``Y`` is
# treated as a vowel when not in word-initial position (mirroring the C
# oracle's behaviour for words like ``city`` → CIT-Y).
_VOWEL_LETTERS: Final[frozenset[str]] = frozenset("AEIOUY")


# Latinate stress-shift suffixes, ported from the suffix-stress rules in
# ``src/dapi/src/lts/l_us_suf.c`` / ``l_us_ru1.c`` (the C oracle's
# stress-shift table; the binary encoding lives in ``suffix_table[]``).
#
# Each entry maps a word-final suffix (matched against the upper-case
# spelling) to the position of the primary-stressed vowel, expressed as
# the number of *spelling-side* vowel groups counted from the last vowel
# of the stem (i.e. 1 = penult-of-stem = vowel immediately before the
# suffix; 2 = antepenult = vowel two groups before the suffix start).
#
# Empirically calibrated against the C oracle (``CAPI.convert_to_phonemes``):
#
#   atomic    -> AX T 'AA M IX K        (-IC,    shift=1: vowel before -IC)
#   ability   -> AX B 'IH L IX T IY     (-ITY,   shift=2: vowel before -L-ITY)
#   national  -> N 'AE SH IX N AX L     (-IONAL, shift=2: vowel before -TION-AL)
#   tradition -> T R AX D 'IH SH IX N   (-ITION, shift=1: vowel before -TION)
#   classical -> K LL 'AE S IX K EL     (-ICAL,  shift=2: vowel before -IC-AL)
#   velocity  -> V IX LL 'AA S IX T IY  (-ICITY, shift=3: vowel 3 groups back)
#   electric  -> AX LL 'EH K T R IX K   (-IC,    shift=1)
#   periodic  -> P IY R IY 'AA D IX K   (-IC,    shift=1)
#   fantastic -> F AX N T 'AE S T IX K  (-IC,    shift=1)
#   magnetic  -> M AX G N 'EH T IX K    (-IC,    shift=1)
#   energetic -> EH N R RJH 'EH T IX K  (-IC,    shift=1)
#
# Longer suffixes are listed first so the matcher picks the most
# specific pattern (``-ICITY`` before ``-ITY``, ``-IONAL`` before
# ``-IAL``/``-AL``, etc.).
_LATINATE_SUFFIXES: Final[tuple[tuple[str, int], ...]] = (
    # The shift is the number of vowel groups counted back from the END
    # of the stem (the portion before the suffix). ``shift = 1`` always
    # means "place primary stress on the last vowel of the stem", which
    # is the standard Latinate behaviour for ``-IC``/``-ITY``/``-ION``
    # and friends. The C oracle has a few longer suffixes (e.g.
    # ``-ICALLY`` from ``-ICAL`` + ``-LY``) that shift further back;
    # those are listed first so the matcher picks the most specific
    # pattern.
    #
    # 6-letter
    ("ICALLY", 1),  # economically: stem=ECONOM, last vowel = O
    # 5-letter
    ("ICITY", 1),  # publicity, electricity: stem ends just before -ICITY
    ("ICIAN", 1),  # musician, physician
    ("ICIAL", 1),  # official, financial
    ("ICIST", 1),  # publicist, classicist
    ("ICISM", 1),  # criticism, classicism
    ("IONAL", 1),  # national, traditional, rational
    ("IATIC", 1),  # dramatic, fanatic (treated as -IC + -IATIC variant)
    # 4-letter
    ("ICAL", 1),  # classical, logical, physical
    ("ICLE", 1),  # particle, vehicle, article
    ("IOUS", 1),  # gracious, ambitious, religious
    ("EOUS", 1),  # gaseous, hideous, igneous
    ("UOUS", 1),  # tenuous, conspicuous, continuous
    ("ITUDE", 1),  # altitude, magnitude, attitude
    ("ITION", 1),  # tradition, addition, condition
    ("ATION", 1),  # nation, creation, station
    ("UTION", 1),  # solution, evolution, resolution
    ("ETION", 1),  # completion, accretion, deletion
    # 3-letter
    ("ITY", 1),  # ability, sanity, velocity
    ("ION", 1),  # mention, vision, religion
    ("IAN", 1),  # Italian, librarian
    ("IAL", 1),  # facial, racial, special
    ("IUM", 1),  # medium, premium, stadium
    ("OUS", 1),  # famous, joyous, generous
    # 2-letter
    ("IC", 1),  # atomic, magnetic, electric
)


def lts(word: str) -> list[str]:
    """Convert an upper-case English word to ARPABET phonemes by rule.

    Walks the word left-to-right, at each step trying every rule in
    declaration order and applying the first whose grapheme matches and
    whose context constraints hold. Always makes progress (default
    single-letter rules exist for every letter).

    A simple stress heuristic is layered on top. By default the first
    vowel in a polysyllabic word receives primary stress (digit ``1``)
    and others receive ``0``. When the word ends in a Latinate
    stress-shift suffix (``-IC``, ``-ITY``, ``-ICAL``, ``-ION``,
    ``-IONAL``, ``-IOUS``, etc., ported from the C oracle's
    ``l_us_suf.c`` rule table), primary stress is repositioned to the
    appropriate stem vowel: e.g. ``atomic`` → ``AH0 T AA1 M IH0 K``,
    ``ability`` → ``AH0 B IH1 L IH0 T IY0``. The lexicon is preferred
    whenever available.

    Args:
        word: Input word in any case; folded to upper-case internally.

    Returns:
        ARPABET phoneme list. May be empty for words consisting solely
        of silent letters (rare).
    """
    text = word.upper()
    raw: list[str] = []
    # Track which spelling-side vowel group produced each phoneme, so we
    # can later map a "stress on the Nth vowel group from the end" rule
    # back onto a phoneme index.
    vowel_group_per_phone: list[int] = []
    last_letter_was_vowel = False
    current_vowel_group = -1
    i = 0
    n = len(text)
    while i < n:
        rule = _match_rule(text, i)
        if rule is None:
            i += 1
            last_letter_was_vowel = False
            continue
        # Detect whether this grapheme starts a new spelling-side vowel
        # group. ``Y`` counts as a vowel only when not word-initial
        # (mirroring the C oracle's "city"-style behaviour).
        first_letter = rule.grapheme[0]
        is_vowel_group = first_letter in _VOWEL_LETTERS and not (first_letter == "Y" and i == 0)
        if is_vowel_group and not last_letter_was_vowel:
            current_vowel_group += 1
        for ph in rule.phones:
            raw.append(ph)
            vowel_group_per_phone.append(current_vowel_group if is_vowel_group else -1)
        # Track the last *letter* (not grapheme) to decide group boundaries.
        last_letter_was_vowel = rule.grapheme[-1] in _VOWEL_LETTERS

        i += len(rule.grapheme)

    total_vowel_groups = current_vowel_group + 1
    stress_group = _latinate_stress_group(text, total_vowel_groups)
    return _add_stress(raw, vowel_group_per_phone, stress_group)


def _latinate_stress_group(text: str, total_vowel_groups: int) -> int | None:
    """Return the 0-based spelling vowel-group index that should bear primary stress.

    Scans ``text`` for a recognised Latinate stress-shift suffix (see
    :data:`_LATINATE_SUFFIXES`) and, when found, maps the suffix's
    ``shift`` (groups counted back from the last stem vowel) into an
    absolute group index. Returns ``None`` when no suffix matches, in
    which case the caller falls back to the default first-vowel rule.
    """
    if total_vowel_groups < 2:  # noqa: PLR2004 -- need at least 2 groups for suffix-shift
        # Monosyllables / single-vowel stems get the default first-vowel
        # stress; suffix-shift rules don't apply.
        return None
    for suffix, shift in _LATINATE_SUFFIXES:
        if not text.endswith(suffix) or len(text) <= len(suffix):
            continue
        # Count vowel groups in the stem (the part before the suffix).
        stem = text[: -len(suffix)]
        stem_groups = _count_vowel_groups(stem, leading_pos=0)
        if stem_groups < shift:
            # Stem is too short for this shift — skip and try the next
            # (less specific) suffix.
            continue
        # The stressed group is ``shift`` groups back from the end of
        # the stem (i.e. ``stem_groups - shift`` in 0-based indexing).
        return stem_groups - shift
    return None


def _count_vowel_groups(text: str, leading_pos: int = 0) -> int:
    """Count contiguous spelling-side vowel groups in ``text``.

    ``leading_pos`` is the starting absolute position within the larger
    word (only used to decide whether a leading ``Y`` is a vowel).
    """
    groups = 0
    last_was_vowel = False
    for idx, ch in enumerate(text):
        is_vowel = ch in _VOWEL_LETTERS and not (ch == "Y" and (leading_pos + idx) == 0)
        if is_vowel and not last_was_vowel:
            groups += 1
        last_was_vowel = is_vowel
    return groups


def _add_stress(
    phones: list[str],
    vowel_group_per_phone: list[int] | None = None,
    stress_group: int | None = None,
) -> list[str]:
    """Annotate vowels with stress digits (CMUDict convention).

    If ``stress_group`` is supplied (from the Latinate suffix matcher),
    primary stress is placed on the first vowel phoneme belonging to
    that spelling-side vowel group. Otherwise the first vowel phoneme
    receives primary stress (the default heuristic).
    """
    vowel_indices = [idx for idx, p in enumerate(phones) if p in _VOWEL_PHONEMES]
    if not vowel_indices:
        return phones
    out = list(phones)
    primary_idx = vowel_indices[0]
    if stress_group is not None and vowel_group_per_phone is not None:
        # Find the first vowel phoneme whose source spelling group is
        # the target stress group. Fall back to the default when no
        # phoneme matches (e.g. the stressed vowel got silenced).
        for idx in vowel_indices:
            if vowel_group_per_phone[idx] == stress_group:
                primary_idx = idx
                break
    for idx in vowel_indices:
        if idx == primary_idx:
            out[idx] = out[idx] + "1"
        else:
            out[idx] = out[idx] + "0"
    return out


def _match_rule(text: str, pos: int) -> _Rule | None:
    """Find the first rule whose grapheme matches at ``pos`` with constraints met."""
    for rule in _RULES:
        if not text.startswith(rule.grapheme, pos):
            continue
        if not _context_ok(text, pos, rule):
            continue
        return rule
    return None


def _context_ok(text: str, pos: int, rule: _Rule) -> bool:
    """Check the left/right context constraints of a rule.

    The ``left`` pattern is matched against the substring ending at
    ``pos`` (so ``"VOWEL$"`` checks the immediately-preceding letter).
    The ``right`` pattern is matched against the substring starting after
    the grapheme. Either being empty disables that side.
    """
    if rule.left and not re.search(rule.left + "$", text[:pos]):
        return False
    if rule.right:
        right_start = pos + len(rule.grapheme)
        if not re.match(rule.right, text[right_start:]):
            return False
    return True
