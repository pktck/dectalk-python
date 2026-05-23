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
    # Word-final ``AH`` is the bare-vowel interjection (``ah``, ``bah``,
    # ``hurrah``): the H is silent and the A is the open back vowel
    # ``AA``, matching the C oracle's ``' aa`` for "ah". Anchored at word
    # end so medial ``ah`` (e.g. ``ahead``) still goes through the default
    # A + H rules.
    _Rule("AH", "", "$", ("AA",)),
    # Word-final ``-ING`` is the productive English present-participle /
    # gerund suffix. The unstressed I in this position is the centralised
    # ``IX`` schwa-like vowel in DECtalk's phoneme set (matches the C
    # oracle's ``ixnx`` for "testing"). Restricted to non-monosyllables
    # via a non-empty left context so "sing" / "ring" / "king" still pick
    # up the default ``IH`` short-i.
    _Rule("ING", r".[^AEIOUY]", "$", ("IX", "NG")),
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
    # Word-final lone I after a consonant is the long-i diphthong (``hi``,
    # ``pi``, ``ski``, ``ti``): matches the C oracle's ``hx' ay`` for
    # "hi". The non-empty left context ensures bare-letter ``I`` (the
    # pronoun) still routes through the lexicon, and that medial / vowel-
    # adjacent ``I`` falls through to the default ``IH``.
    _Rule("I", r"[BCDFGHJKLMNPQRSTVWXZ]", "$", ("AY",)),
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
    # ---- Latinate suffix palatalisation -------------------------------
    # The C LTS, via the suffix tables in `l_us_suf.c`, palatalises
    # consonant + front-vowel clusters at the end of Latinate words:
    #
    #   -TURE  -> CH ER       (nature, fixture, future, picture, culture)
    #   -TION  -> SH AH N     (nation, station, motion)
    #   -SION  -> SH AH N     after a consonant (mansion, pension, mission)
    #   -SION  -> ZH AH N     after a vowel (vision, fusion, occasion)
    #   -CIAN  -> SH AH N     (musician, physician, electrician)
    #   -CIAL  -> SH AH L     (social, special, official, racial)
    #   -TIAL  -> SH AH L     (partial, initial, essential)
    #   -CIOUS -> SH AH S     (delicious, gracious, vicious)
    #   -TIOUS -> SH AH S     (cautious, fictitious, ambitious)
    #
    # These multi-letter rules sit at the top of the consonant rule list
    # so they win against the single-letter T/S/C defaults that would
    # otherwise emit literal `T Y UW R` / `S IH AH N` etc. Each rule is
    # anchored at the right with ``$`` so it only fires at word-final
    # position; mid-word ``-tion-`` etc. fall through to default rules.
    _Rule("TURE", "", "$", ("CH", "ER")),
    _Rule("TION", "", "$", ("SH", "AH", "N")),
    # -SSION (mission, expression, discussion) collapses to a single
    # SH cluster — the doubled S would otherwise emit `S SH AH N`.
    _Rule("SSION", "", "$", ("SH", "AH", "N")),
    _Rule("SION", "[AEIOU]", "$", ("ZH", "AH", "N")),
    _Rule("SION", "[BCDFGHJKLMNPQRSTVWXZ]", "$", ("SH", "AH", "N")),
    _Rule("CIAN", "", "$", ("SH", "AH", "N")),
    _Rule("CIAL", "", "$", ("SH", "AH", "L")),
    _Rule("TIAL", "", "$", ("SH", "AH", "L")),
    _Rule("CIOUS", "", "$", ("SH", "AH", "S")),
    _Rule("TIOUS", "", "$", ("SH", "AH", "S")),
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
    {"AA", "AE", "AH", "AO", "AX", "EH", "ER", "IH", "IX", "IY", "UH", "UW",
     "AY", "AW", "EY", "OW", "OY"}
)  # fmt: skip


def lts(word: str) -> list[str]:
    """Convert an upper-case English word to ARPABET phonemes by rule.

    Walks the word left-to-right, at each step trying every rule in
    declaration order and applying the first whose grapheme matches and
    whose context constraints hold. Always makes progress (default
    single-letter rules exist for every letter).

    A simple stress heuristic is layered on top: the first vowel in
    polysyllabic words receives primary stress (digit ``1``), other
    vowels secondary (``2`` for monosyllables, ``0`` for the rest). This
    is wrong roughly half the time for English nouns/verbs, but is
    enough to make the prosody pass produce audibly accented output for
    out-of-lexicon words. The lexicon is preferred whenever available.

    Args:
        word: Input word in any case; folded to upper-case internally.

    Returns:
        ARPABET phoneme list. May be empty for words consisting solely
        of silent letters (rare).
    """
    text = word.upper()
    raw: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        rule = _match_rule(text, i)
        if rule is None:
            # Unknown character — skip it rather than raise. This handles
            # apostrophes / hyphens leaking into the LTS path.
            i += 1
            continue
        raw.extend(rule.phones)
        i += len(rule.grapheme)

    return _add_stress(raw)


def _add_stress(phones: list[str]) -> list[str]:
    """Annotate vowels with simple stress digits (CMUDict convention)."""
    vowel_indices = [idx for idx, p in enumerate(phones) if p in _VOWEL_PHONEMES]
    if not vowel_indices:
        return phones
    out = list(phones)
    primary_idx = vowel_indices[0]
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
