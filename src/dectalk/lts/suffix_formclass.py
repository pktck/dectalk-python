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
  mask (``postman`` → ``FC_NOUN`` via the ``-man`` rule) without any
  dictionary lookup.

The rule chains are decoded at import time from the byte-verbatim
``suffix_table`` / ``suffix_index`` arrays in
:mod:`dectalk.lts.suffix_data` (parity-tested byte-for-byte against
``l_us_suf.c`` by ``tests/unit/test_lts_suffix_data.py``), so this
module carries no duplicate copy of the table. The walk in
:func:`suffix_form_class` mirrors the C matcher: chains are selected
by the word's final letter, rules are tried in linked-list order, and
the suffix match may not consume the word's first vowel (the
``str_vowel`` guard in ``ls_suff_suffix_find``).

Phoneme derivation is *not* modelled here — only the form-class mask
(and the stripped root, so the caller can resolve homograph roots like
``tears`` → ``tear``). The phoneme side lives in the stem-stripping
branches of :func:`dectalk.api.speak.text_to_dectalk_phonemes`.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from typing import Final

from dectalk.lts.suffix_data import suffix_index, suffix_table

_VOWELS: Final[str] = "aeiou"
"""Letters flagged ``OO`` (vowel) in the US ``lsctype[]`` table
(``l_us_con.c``); ``y`` is explicitly not a vowel there."""

# Parse-table tokens from ls_suff.c (must match the suffix dictionary
# compiler).
_SF_END: Final[int] = 0xFF
_SF_STRIP: Final[int] = 0xFE
_SF_FC: Final[int] = 0xFD
_SF_REPLACE: Final[int] = 0xFC
_SF_REPLACE_WITH: Final[int] = 0xFB
_SF_REPLACE_END: Final[int] = 0xFA
_SF_RECURSE: Final[int] = 0xF9
_SF_PHONES: Final[int] = 0xF8
_SF_PHONES_END: Final[int] = 0xF7

_CHAIN_TERMINATOR: Final[int] = 0xFFFF
"""``suffix_index`` / ``next`` value marking the end of a chain."""

_ALPHA_CHAINS: Final[int] = 26
"""Chains 0-25 are ``a``-``z``; index 26 serves non-alphabetic finals
(apostrophes — ``suffix_index[26]`` in ``ls_suff_suffix_find``)."""


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


def _decode_rule(offset: int) -> tuple[int, SuffixRule | None]:  # noqa: PLR0912 - mirrors the C record layout's per-token branches
    """Decode one ``struct suff_rule`` record at ``offset``.

    The record layout (``ls_dict.h``) is ``U32 next``, ``U32 fc``,
    then the byte-coded rule: the reversed suffix text, an
    ``SF_STRIP``/``SF_FC`` marker, and (for strip rules) the
    ``SF_REPLACE`` alternatives with optional ``SF_RECURSE`` and
    ``SF_PHONES`` payloads.

    Args:
        offset: Byte offset of the record in :data:`suffix_table`.

    Returns:
        ``(next_offset, rule)``; ``rule`` is ``None`` for the empty
        sentinel record at the end of the table.
    """
    nxt = int.from_bytes(suffix_table[offset : offset + 4], "little")
    fc = int.from_bytes(suffix_table[offset + 4 : offset + 8], "little")
    j = offset + 8
    suffix_rev: list[str] = []
    while j < len(suffix_table) and suffix_table[j] < _SF_PHONES_END:
        suffix_rev.append(chr(suffix_table[j]))
        j += 1
    if j >= len(suffix_table) or not suffix_rev:
        return nxt, None
    suffix = "".join(reversed(suffix_rev))
    kind = suffix_table[j]
    if kind == _SF_FC:
        return nxt, SuffixRule(suffix, fc, None)
    if kind != _SF_STRIP:
        return nxt, None
    j += 1
    repls: list[tuple[str, str]] = []
    while j < len(suffix_table) and suffix_table[j] != _SF_END:
        if suffix_table[j] == _SF_REPLACE:
            j += 1
            extra: list[str] = []
            while j < len(suffix_table) and suffix_table[j] < _SF_PHONES_END:
                extra.append(chr(suffix_table[j]))
                j += 1
            if j >= len(suffix_table) or suffix_table[j] != _SF_REPLACE_WITH:
                break
            j += 1
            repl: list[str] = []
            while j < len(suffix_table) and suffix_table[j] < _SF_PHONES_END:
                repl.append(chr(suffix_table[j]))
                j += 1
            if j >= len(suffix_table) or suffix_table[j] != _SF_REPLACE_END:
                break
            j += 1
            if j < len(suffix_table) and suffix_table[j] == _SF_RECURSE:
                j += 1
            # ``extra`` is matched backwards from the strip point,
            # so it reverses like the suffix; ``repl`` is stored
            # forward (it is copied verbatim into the buffer).
            repls.append(("".join(reversed(extra)), "".join(repl)))
        elif suffix_table[j] == _SF_PHONES:
            while j < len(suffix_table) and suffix_table[j] != _SF_PHONES_END:
                j += 1
            j += 1
        else:
            j += 1
    return nxt, SuffixRule(suffix, fc, tuple(repls))


def _decode_chains() -> dict[str, tuple[SuffixRule, ...]]:
    """Decode all 27 per-letter chains from the verbatim byte table."""
    chains: dict[str, tuple[SuffixRule, ...]] = {}
    for letter_i, start in enumerate(suffix_index):
        if start == _CHAIN_TERMINATOR:
            continue
        letter = chr(ord("a") + letter_i) if letter_i < _ALPHA_CHAINS else "'"
        rules: list[SuffixRule] = []
        offset = start
        first = True
        # Offset 0 is a valid first record (the 's' chain); a zero
        # ``next`` pointer otherwise terminates the walk.
        while (offset != _CHAIN_TERMINATOR and (offset != 0 or first)) and offset < len(
            suffix_table
        ):
            first = False
            offset, rule = _decode_rule(offset)
            if rule is not None:
                rules.append(rule)
        if rules:
            chains[letter] = tuple(rules)
    return chains


_SUFFIX_CHAINS: Final[dict[str, tuple[SuffixRule, ...]]] = _decode_chains()
"""Per-final-letter suffix rule chains, decoded from ``l_us_suf.c``'s
byte-verbatim ``suffix_table`` (non-alphabetic finals share the
index-26 chain, keyed ``"'"``)."""


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
