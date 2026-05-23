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
    _Rule("OUGH", "", "T", ("AO",)),  # bought, thought
    _Rule("OUGH", "", "", ("AH", "F")),  # rough
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
