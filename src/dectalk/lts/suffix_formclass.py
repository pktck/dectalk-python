"""Suffix-derived form-class tagging from ``l_us_suf.c`` (issue #295).

The C runtime tags every word with a 32-bit form-class mask before the
homograph disambiguator (``ls_homo_homo``) consults it as left context.
Dictionary words carry their entry's mask; words *outside* the main
dictionary get their mask from the suffix engine
(``ls_suff_suffix_find`` in ``src/dapi/src/lts/ls_suff.c``):

- **Strip rules** (``SF_STRIP``): the suffix is stripped, replacement
  variants re-derive the root (``closed`` → ``close``, ``married`` →
  ``marry``), and when the root hits the main dictionary the *rule's*
  fc mask is kept for the word (``fc_struct[fc_index] = stp->fc``,
  ls_suff.c line 248). A miss resets the mask to 0 and the chain walk
  continues.
- **FC-tag rules** (``SF_FC``): the suffix match alone assigns the
  mask (``man`` → ``FC_NOUN`` via the ``-man`` rule) without any
  dictionary lookup.

:data:`_SUFFIX_CHAINS` is a faithful extraction of the generated
``suffix_table[]`` / ``suffix_index[]`` arrays in
``src/dapi/src/lts/l_us_suf.c`` (rule text, per-rule fc, replacement
alternatives, chain order). The walk in :func:`suffix_form_class`
mirrors the C matcher: chains are selected by the word's final letter,
rules are tried in chain order, and the suffix match may not consume
the word's first vowel (the ``str_vowel`` guard in
``ls_suff_suffix_find``).

Phoneme derivation is *not* modelled here — only the form-class mask
(and the stripped root, so the caller can resolve homograph roots like
``tears`` → ``tear``). The phoneme side lives in the stem-stripping
branches of :func:`dectalk.api.speak.text_to_dectalk_phonemes`.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from typing import Final

_VOWELS: Final[str] = "aeiou"
"""Letters flagged ``OO`` (vowel) in the US ``lsctype[]`` table
(``l_us_con.c``); ``y`` is explicitly not a vowel there."""


@dataclass(frozen=True, slots=True)
class SuffixRule:
    """One rule from the ``suffix_table[]`` chain.

    Attributes:
        suffix: Literal word-final text the rule matches (stored
            forward; the C table stores it reversed for the
            back-to-front matcher).
        fc: ``FC_*`` mask the rule assigns (``stp->fc``).
        replacements: ``None`` for an ``SF_FC`` tag-only rule.
            For ``SF_STRIP`` rules, the ordered ``(extra, repl)``
            alternatives: ``extra`` is additional word-final text
            (before the suffix) consumed by the variant, ``repl`` is
            the text appended to re-derive the root. E.g. the ``-ed``
            rule's ``("", "e")`` maps ``closed`` → ``close`` and its
            ``("i", "y")`` maps ``married`` → ``marry``.
    """

    suffix: str
    fc: int
    replacements: tuple[tuple[str, str], ...] | None


# Faithful extraction of l_us_suf.c suffix_table[] (rule text, fc,
# replacement alternatives, chain order). Keys are the word-final
# letter (suffix_index[] is indexed by last letter; non a-z characters
# share the index-26 chain, keyed "'" here).
_SUFFIX_CHAINS: Final[dict[str, tuple[SuffixRule, ...]]] = {
    "'": (
        SuffixRule("s'", 0x00000001, (("", ""), ("", ""))),
        SuffixRule("dell'", 0x00000400, None),
    ),
    "a": (SuffixRule("a", 0x00000400, None),),
    "c": (
        SuffixRule("otic", 0x00000001, None),
        SuffixRule("obic", 0x00000001, None),
        SuffixRule("ostic", 0x00000001, None),
        SuffixRule("istic", 0x00000001, None),
        SuffixRule("atric", 0x00000001, None),
        SuffixRule("scopic", 0x00000001, None),
        SuffixRule("metric", 0x00000001, None),
        SuffixRule("graphic", 0x00000001, None),
        SuffixRule("ic", 0x00000401, None),
    ),
    "d": (
        SuffixRule(
            "ed",
            0x00000080,
            (
                ("", "e"),
                ("", ""),
                ("i", "y"),
                ("bb", "b"),
                ("cc", "c"),
                ("dd", "d"),
                ("gg", "g"),
                ("hh", "h"),
                ("jj", "j"),
                ("kk", "k"),
                ("mm", "m"),
                ("nn", "n"),
                ("pp", "p"),
                ("rr", "r"),
                ("tt", "t"),
                ("vv", "v"),
                ("xx", "x"),
                ("zz", "z"),
            ),
        ),
        SuffixRule("hood", 0x00000400, (("", ""),)),
        SuffixRule("yard", 0x00000400, None),
        SuffixRule("ward", 0x00000001, None),
        SuffixRule("hand", 0x00000400, None),
        SuffixRule("wald", 0x00000400, None),
        SuffixRule("feld", 0x00000400, None),
        SuffixRule("gaard", 0x00000400, None),
        SuffixRule("chord", 0x00000400, None),
        SuffixRule("id", 0x00000401, None),
    ),
    "e": (
        SuffixRule("able", 0x00000001, (("", ""), ("", "e"))),
        SuffixRule("ize", 0x00020000, (("", ""),)),
        SuffixRule("cle", 0x00000400, None),
        SuffixRule("cede", 0x00020000, None),
        SuffixRule("edge", 0x00000400, None),
        SuffixRule("some", 0x00000001, None),
        SuffixRule("wise", 0x00000001, None),
        SuffixRule("ware", 0x00000400, None),
        SuffixRule("trouble", 0x00000400, None),
        SuffixRule("uble", 0x00000001, None),
        SuffixRule("ture", 0x00000400, None),
        SuffixRule("tude", 0x00000400, None),
        SuffixRule("time", 0x00000400, None),
        SuffixRule("sure", 0x00000400, None),
        SuffixRule("stle", 0x00000001, None),
        SuffixRule("pose", 0x00020000, None),
        SuffixRule("otte", 0x00000400, None),
        SuffixRule("oire", 0x00000400, None),
        SuffixRule("like", 0x00000001, None),
        SuffixRule("iqe", 0x00000400, None),
        SuffixRule("iere", 0x00000400, None),
        SuffixRule("ible", 0x00000001, None),
        SuffixRule("iate", 0x00000001, None),
        SuffixRule("iage", 0x00000400, None),
        SuffixRule("hole", 0x00000400, None),
        SuffixRule("ette", 0x00000400, None),
        SuffixRule("esse", 0x00000400, None),
        SuffixRule("ence", 0x00000400, None),
        SuffixRule("dale", 0x00000400, None),
        SuffixRule("cake", 0x00000400, None),
        SuffixRule("ance", 0x00000400, None),
        SuffixRule("aise", 0x00000400, None),
        SuffixRule("aire", 0x00000001, None),
        SuffixRule("ville", 0x00000400, None),
        SuffixRule("utive", 0x00000001, None),
        SuffixRule("uance", 0x00000400, None),
        SuffixRule("stone", 0x00000400, None),
        SuffixRule("scope", 0x00000400, None),
        SuffixRule("plane", 0x00000400, None),
        SuffixRule("phone", 0x00000400, None),
        SuffixRule("phobe", 0x00000400, None),
        SuffixRule("place", 0x00000400, None),
        SuffixRule("metre", 0x00000400, None),
        SuffixRule("loge", 0x00000400, None),
        SuffixRule("litre", 0x00000400, None),
        SuffixRule("ienne", 0x00000400, None),
        SuffixRule("ielle", 0x00000400, None),
        SuffixRule("icide", 0x00000400, None),
        SuffixRule("grade", 0x00000001, None),
        SuffixRule("esqe", 0x00000001, None),
        SuffixRule("vande", 0x00000400, None),
        SuffixRule("delle", 0x00000400, None),
        SuffixRule("scape", 0x00000400, None),
        SuffixRule("logue", 0x00000400, None),
        SuffixRule("eille", 0x00000400, None),
        SuffixRule("ceive", 0x00020000, None),
        SuffixRule("sphere", 0x00000400, None),
        SuffixRule("finkle", 0x00000400, None),
        SuffixRule("culture", 0x00000001, None),
        SuffixRule("machine", 0x00000400, None),
        SuffixRule("se", 0x00020400, None),
        SuffixRule("que", 0x00000401, None),
        SuffixRule("ile", 0x00000401, None),
        SuffixRule("ime", 0x00000401, None),
        SuffixRule("ive", 0x00000401, None),
        SuffixRule("ese", 0x00000401, None),
        SuffixRule("ice", 0x00020400, None),
        SuffixRule("ace", 0x00020400, None),
        SuffixRule("age", 0x00020400, None),
        SuffixRule("ale", 0x00000401, None),
        SuffixRule("type", 0x00000401, None),
        SuffixRule("oge", 0x00000401, None),
        SuffixRule("ige", 0x00020400, None),
        SuffixRule("ease", 0x00020400, None),
    ),
    "f": (
        SuffixRule("kopf", 0x00000400, None),
        SuffixRule("dorf", 0x00000400, None),
    ),
    "g": (
        SuffixRule(
            "ing",
            0x00000200,
            (
                ("", "e"),
                ("", ""),
                ("i", "y"),
                ("bb", "b"),
                ("cc", "c"),
                ("dd", "d"),
                ("gg", "g"),
                ("hh", "h"),
                ("jj", "j"),
                ("kk", "k"),
                ("mm", "m"),
                ("nn", "n"),
                ("pp", "p"),
                ("tt", "t"),
                ("vv", "v"),
                ("xx", "x"),
                ("zz", "z"),
            ),
        ),
        SuffixRule("berg", 0x00000400, None),
    ),
    "h": (
        SuffixRule("ish", 0x00020001, (("", ""),)),
        SuffixRule("tsch", 0x00000400, None),
        SuffixRule("ghth", 0x00000400, None),
        SuffixRule("vich", 0x00000400, None),
        SuffixRule("path", 0x00000400, None),
        SuffixRule("ieth", 0x00000001, None),
        SuffixRule("fish", 0x00000400, None),
        SuffixRule("bach", 0x00000400, None),
        SuffixRule("augh", 0x00000400, None),
        SuffixRule("vitch", 0x00000400, None),
        SuffixRule("graph", 0x00000400, None),
        SuffixRule("burgh", 0x00000400, None),
        SuffixRule("baugh", 0x00000400, None),
        SuffixRule("evitch", 0x00000400, None),
        SuffixRule("borough", 0x00000400, None),
    ),
    "i": (
        SuffixRule("ski", 0x00000400, None),
        SuffixRule("uchi", 0x00000400, None),
        SuffixRule("olli", 0x00000400, None),
        SuffixRule("ishi", 0x00000400, None),
        SuffixRule("etti", 0x00000400, None),
        SuffixRule("elli", 0x00000400, None),
    ),
    "k": (
        SuffixRule("mark", 0x00000400, None),
        SuffixRule("szek", 0x00000400, None),
        SuffixRule("neck", 0x00000400, None),
        SuffixRule("czyk", 0x00000400, None),
        SuffixRule("czuk", 0x00000400, None),
        SuffixRule("czek", 0x00000400, None),
        SuffixRule("czak", 0x00000400, None),
        SuffixRule("book", 0x00000400, None),
        SuffixRule("beck", 0x00000400, None),
    ),
    "l": (
        SuffixRule("ful", 0x00000001, (("", ""), ("i", "y"))),
        SuffixRule("cal", 0x00000001, None),
        SuffixRule("pel", 0x00020000, None),
        SuffixRule("will", 0x00000400, None),
        SuffixRule("tual", 0x00000001, None),
        SuffixRule("tial", 0x00000001, None),
        SuffixRule("tail", 0x00000400, None),
        SuffixRule("sual", 0x00000001, None),
        SuffixRule("mail", 0x00000400, None),
        SuffixRule("inal", 0x00000001, None),
        SuffixRule("hill", 0x00000400, None),
        SuffixRule("bell", 0x00000400, None),
        SuffixRule("ball", 0x00000400, None),
        SuffixRule("tural", 0x00000001, None),
        SuffixRule("gonal", 0x00000001, None),
        SuffixRule("ional", 0x00000001, None),
        SuffixRule("mental", 0x00000001, None),
        SuffixRule("icidal", 0x00000001, None),
        SuffixRule("ennial", 0x00000001, None),
        SuffixRule("ational", 0x00000001, None),
        SuffixRule("ational", 0x00000001, None),
        SuffixRule("cultural", 0x00000001, None),
        SuffixRule("al", 0x00000401, None),
        SuffixRule("cial", 0x00000401, None),
    ),
    "m": (
        SuffixRule("dom", 0x00000400, (("", ""),)),
        SuffixRule("ism", 0x00000400, (("", ""),)),
        SuffixRule("sm", 0x00000400, None),
        SuffixRule("gram", 0x00000400, None),
        SuffixRule("heim", 0x00000400, None),
        SuffixRule("baum", 0x00000400, None),
        SuffixRule("ingham", 0x00000400, None),
    ),
    "n": (
        SuffixRule("men", 0x00000400, None),
        SuffixRule("man", 0x00000400, None),
        SuffixRule("ion", 0x00000400, None),
        SuffixRule("teen", 0x00000400, None),
        SuffixRule("sten", 0x00000400, None),
        SuffixRule("sohn", 0x00000400, None),
        SuffixRule("sian", 0x00000400, None),
        SuffixRule("mann", 0x00000400, None),
        SuffixRule("lian", 0x00000400, None),
        SuffixRule("ican", 0x00000400, None),
        SuffixRule("geon", 0x00000400, None),
        SuffixRule("cian", 0x00000400, None),
        SuffixRule("lein", 0x00000400, None),
        SuffixRule("bahn", 0x00000400, None),
        SuffixRule("auen", 0x00000400, None),
        SuffixRule("ghlin", 0x00000400, None),
        SuffixRule("arian", 0x00000001, None),
        SuffixRule("stein", 0x00000400, None),
        SuffixRule("ington", 0x00000400, None),
        SuffixRule("vanden", 0x00000400, None),
        SuffixRule("hausen", 0x00000400, None),
        SuffixRule("children", 0x00000400, None),
        SuffixRule("an", 0x00000401, None),
        SuffixRule("ain", 0x00020400, None),
        SuffixRule("tian", 0x00000401, None),
    ),
    "o": (
        SuffixRule("moto", 0x00000400, None),
        SuffixRule("illo", 0x00000400, None),
        SuffixRule("etto", 0x00000400, None),
        SuffixRule("enko", 0x00000400, None),
        SuffixRule("ello", 0x00000400, None),
        SuffixRule("eiro", 0x00000400, None),
        SuffixRule("boro", 0x00000400, None),
        SuffixRule("pseudo", 0x00000001, None),
    ),
    "p": (
        SuffixRule("ship", 0x00000400, (("", ""),)),
        SuffixRule("shop", 0x00000400, None),
    ),
    "r": (
        SuffixRule(
            "er",
            0x00000403,
            (
                ("", "e"),
                ("", ""),
                ("i", "y"),
                ("bb", "b"),
                ("cc", "c"),
                ("dd", "d"),
                ("gg", "g"),
                ("hh", "h"),
                ("jj", "j"),
                ("kk", "k"),
                ("mm", "m"),
                ("nn", "n"),
                ("pp", "p"),
                ("rr", "r"),
                ("tt", "t"),
                ("vv", "v"),
                ("xx", "x"),
                ("zz", "z"),
            ),
        ),
        SuffixRule("or", 0x00000401, (("", "e"),)),
        SuffixRule("cur", 0x00020000, None),
        SuffixRule("fer", 0x00020000, None),
        SuffixRule("oir", 0x00000400, None),
        SuffixRule("tor", 0x00000400, None),
        SuffixRule("euer", 0x00000400, None),
        SuffixRule("eier", 0x00000400, None),
        SuffixRule("ular", 0x00000001, None),
        SuffixRule("izer", 0x00000400, None),
        SuffixRule("iour", 0x00000400, None),
        SuffixRule("auer", 0x00000400, None),
        SuffixRule("meter", 0x00000400, None),
        SuffixRule("maker", 0x00000400, None),
        SuffixRule("liter", 0x00000400, None),
        SuffixRule("color", 0x00000001, None),
        SuffixRule("aier", 0x00000400, None),
        SuffixRule("meyer", 0x00000400, None),
        SuffixRule("meier", 0x00000400, None),
        SuffixRule("coeur", 0x00000400, None),
        SuffixRule("soever", 0x00002000, None),
        SuffixRule("vander", 0x00000400, None),
        SuffixRule("ometer", 0x00000400, None),
        SuffixRule("hoffer", 0x00000400, None),
        SuffixRule("hauser", 0x00000400, None),
        SuffixRule("felder", 0x00000400, None),
        SuffixRule("dorfer", 0x00000400, None),
        SuffixRule("burger", 0x00000400, None),
        SuffixRule("berger", 0x00000400, None),
        SuffixRule("becker", 0x00000400, None),
        SuffixRule("grapher", 0x00000400, None),
        SuffixRule("weather", 0x00000400, None),
        SuffixRule("thunder", 0x00000400, None),
        SuffixRule("meister", 0x00000400, None),
        SuffixRule("counter", 0x00000400, None),
        SuffixRule("doerffer", 0x00000400, None),
        SuffixRule("ar", 0x00000401, None),
    ),
    "s": (
        SuffixRule("s", 0x00020400, (("", ""), ("", ""))),
        SuffixRule("'s", 0x00020001, (("", ""), ("", ""))),
        SuffixRule("es", 0x00020400, (("", "e"), ("", ""))),
        SuffixRule("ies", 0x00020400, (("", "y"), ("", ""))),
        SuffixRule("ers", 0x00020400, (("", "e"), ("", ""), ("i", "y"))),
        SuffixRule(
            "ings",
            0x00000400,
            (
                ("", "e"),
                ("", ""),
                ("i", "y"),
                ("bb", "b"),
                ("cc", "c"),
                ("dd", "d"),
                ("gg", "g"),
                ("hh", "h"),
                ("jj", "j"),
                ("kk", "k"),
                ("mm", "m"),
                ("nn", "n"),
                ("pp", "p"),
                ("rr", "r"),
                ("tt", "t"),
                ("vv", "v"),
                ("xx", "x"),
                ("zz", "z"),
            ),
        ),
        SuffixRule("less", 0x00000001, (("", ""),)),
        SuffixRule("ness", 0x00000400, (("", ""), ("i", "y"))),
        SuffixRule("ous", 0x00000001, None),
        SuffixRule("us", 0x00000400, None),
        SuffixRule("is", 0x00000400, None),
        SuffixRule("ics", 0x00000400, None),
        SuffixRule("polos", 0x00000400, None),
        SuffixRule("selves", 0x00002000, None),
        SuffixRule("poulos", 0x00000400, None),
    ),
    "t": (
        SuffixRule("ment", 0x00000400, (("", ""), ("i", "y"))),
        SuffixRule("mit", 0x00020000, None),
        SuffixRule("iest", 0x00000001, None),
        SuffixRule("uent", 0x00000001, None),
        SuffixRule("uant", 0x00000001, None),
        SuffixRule("stat", 0x00000400, None),
        SuffixRule("port", 0x00000400, None),
        SuffixRule("iett", 0x00000400, None),
        SuffixRule("cient", 0x00000001, None),
        SuffixRule("ient", 0x00000400, None),
        SuffixRule("iant", 0x00000001, None),
        SuffixRule("crat", 0x00000400, None),
        SuffixRule("cast", 0x00000400, None),
        SuffixRule("ault", 0x00000400, None),
        SuffixRule("uplet", 0x00000400, None),
        SuffixRule("sight", 0x00000400, None),
        SuffixRule("qist", 0x00000400, None),
        SuffixRule("qent", 0x00000001, None),
        SuffixRule("olent", 0x00000001, None),
        SuffixRule("eault", 0x00000400, None),
        SuffixRule("veldt", 0x00000400, None),
        SuffixRule("stadt", 0x00000400, None),
        SuffixRule("horst", 0x00000400, None),
        SuffixRule("plicit", 0x00000001, None),
        SuffixRule("logist", 0x00000400, None),
        SuffixRule("thought", 0x00000400, None),
        SuffixRule("schmidt", 0x00000400, None),
        SuffixRule("ent", 0x00000401, None),
        SuffixRule("ant", 0x00000401, None),
        SuffixRule("ident", 0x00000401, None),
    ),
    "u": (
        SuffixRule("sshiuu", 0x00000400, (("", ""),)),
        SuffixRule("ieau", 0x00000400, None),
        SuffixRule("chau", 0x00000400, None),
    ),
    "x": (
        SuffixRule("eaux", 0x00000400, None),
        SuffixRule("flex", 0x00000400, None),
    ),
    "y": (
        SuffixRule("ify", 0x00020000, (("", ""),)),
        SuffixRule("ly", 0x00000002, (("", ""), ("b", "ble"))),
        SuffixRule("ogy", 0x00000400, None),
        SuffixRule("ity", 0x00000400, None),
        SuffixRule("pathy", 0x00000400, None),
        SuffixRule("thy", 0x00000001, None),
        SuffixRule("tory", 0x00000001, None),
        SuffixRule("mony", 0x00000400, None),
        SuffixRule("iety", 0x00000400, None),
        SuffixRule("ency", 0x00000400, None),
        SuffixRule("ancy", 0x00000400, None),
        SuffixRule("bury", 0x00000400, None),
        SuffixRule("body", 0x00002000, None),
        SuffixRule("scopy", 0x00000400, None),
        SuffixRule("metry", 0x00000400, None),
        SuffixRule("berry", 0x00000400, None),
        SuffixRule("archy", 0x00000400, None),
        SuffixRule("ansky", 0x00000400, None),
        SuffixRule("ocracy", 0x00000400, None),
        SuffixRule("graphy", 0x00000400, None),
        SuffixRule("ography", 0x00000400, None),
        SuffixRule("country", 0x00000400, None),
        SuffixRule("ty", 0x00000401, None),
        SuffixRule("cy", 0x00000401, None),
        SuffixRule("fy", 0x00020001, None),
        SuffixRule("gy", 0x00000401, None),
        SuffixRule("chy", 0x00000401, None),
        SuffixRule("tuary", 0x00000401, None),
    ),
    "z": (
        SuffixRule("szcz", 0x00000400, None),
        SuffixRule("witz", 0x00000400, None),
        SuffixRule("wicz", 0x00000400, None),
        SuffixRule("vitz", 0x00000400, None),
        SuffixRule("fitz", 0x00000400, None),
        SuffixRule("iewicz", 0x00000400, None),
        SuffixRule("kiewicz", 0x00000400, None),
    ),
}
"""Per-final-letter suffix rule chains, verbatim from ``l_us_suf.c``."""


def suffix_form_class(
    word: str,
    known_words: Container[str],
) -> tuple[int, str | None, str | None]:
    """Mimic ``ls_suff_suffix_find``'s form-class tagging for one word.

    Walks the word's final-letter chain in table order. A strip rule
    applies when one of its replacement variants re-derives a root
    contained in ``known_words`` (the main-dictionary mimic); an FC
    rule applies on the bare suffix match. The first applicable rule
    wins, exactly like the C chain walk.

    Args:
        word: The word to tag (any case; folded to lower internally).
        known_words: Membership test for the main dictionary —
            upper-cased words (e.g. the form-class sidecar's key set).

    Returns:
        ``(fc, root, suffix)``:

        - ``fc`` — the matched rule's form-class mask, or ``0`` when
          no rule applies (the C leaves ``fc_struct`` at 0 and the
          BATS#705 noun fallback kicks in at homograph time).
        - ``root`` — upper-cased dictionary root for strip rules
          (``TEARS`` → ``TEAR``); ``None`` for FC rules / no match.
        - ``suffix`` — the matched rule's suffix text, or ``None``.
    """
    w = word.lower()
    if not w:
        return 0, None, None
    last = w[-1]
    chain = _SUFFIX_CHAINS.get(last if "a" <= last <= "z" else "'", ())
    first_vowel = next((i for i, ch in enumerate(w) if ch in _VOWELS), None)
    for rule in chain:
        if not w.endswith(rule.suffix) or len(w) == len(rule.suffix):
            continue
        base_len = len(w) - len(rule.suffix)
        # str_vowel guard: the suffix match may not reach the word's
        # first vowel (ls_suff_suffix_find breaks at that pointer).
        if first_vowel is not None and base_len <= first_vowel:
            continue
        if rule.replacements is None:
            return rule.fc, None, rule.suffix
        base = w[:base_len]
        for extra, repl in rule.replacements:
            if extra:
                if not base.endswith(extra):
                    continue
                root = base[: -len(extra)] + repl
            else:
                root = base + repl
            if root and root.upper() in known_words:
                return rule.fc, root.upper(), rule.suffix
        # Strip rule found no dictionary root: the C resets the fc to
        # 0 and keeps walking the chain.
    return 0, None, None


__all__ = ["SuffixRule", "suffix_form_class"]
