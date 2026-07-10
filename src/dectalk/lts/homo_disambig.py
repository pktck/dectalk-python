"""Form-class homograph disambiguation (``ls_homo_homo``).

Faithful port of the entry-selection tail of :func:`ls_homo_homo` from
``src/dapi/src/lts/ls_homo.c`` (the ``!NEW_LTS`` build the oracle
binary uses — ``NEW_LTS`` is commented out in ``dectalkf_klsyn.h``),
reworked for issue #295 to consume the *real* runtime form-class
masks instead of the collapsed noun/verb/adjective bits the previous
version carried.

How the C runtime decides between a homograph's two dictionary
entries (``close`` → ``kl'oz``/``kl'os``, ``wind`` → ``w'Ind``/
``w'And``, ...):

1. The dictionary compiler (``src/dapi/src/dic/dic_comm.c``) stores
   the pair adjacently and flags both rows ``FC_HOMOGRAPH``; the
   primary (``P``) row additionally carries ``FC_CHARACTER``.
2. ``ls_dict_find_word`` detects the flag and calls ``ls_homo_homo``,
   which settles on ``entry_primary`` = the ``P`` row and
   ``entry_secondary`` = the ``S`` row.
3. The first word of a sentence always takes the primary entry
   (``fc_index == 1`` branch, ls_homo.c line 355).
4. An unknown previous word (``fc_struct == 0``) is treated as a noun
   — and the noun mask is *written back* into ``fc_struct``, so later
   context checks see it too (BATS#705, ls_homo.c line 371).
5. The 27-rule :data:`~dectalk.lts.homo_table.homo_table` runs in
   order. A rule applies when its ``h_suffix`` bits are all present
   in the *current* word's pre-set mask (zero for plain dictionary
   hits; the suffix engine's mask for stripped derivations like
   ``tears`` or ``winding``) and its ``h_context`` bits intersect the
   previous word's mask — or, when the previous word is an adverb,
   the word before that (GL 3/3/1997 fall-through).
6. ``h_select``: keep the primary if it carries a selected bit, else
   swap to the secondary if it does. ``h_elim``: keep the primary if
   the *secondary* carries an eliminated bit, else swap if the
   primary does. Either match ends the loop; no match falls through
   to the next rule, and the primary wins by default.

The form-class masks come from the ``formclass_us.txt`` sidecar
(:func:`dectalk.dic.markers.load_formclass_lexicon`) — the same masks
embedded in the runtime ``dtalk_us.dic`` — and the suffix-derived
masks from :func:`dectalk.lts.suffix_formclass.suffix_form_class`.

References:
- ``src/dapi/src/lts/ls_homo.c`` — :func:`ls_homo_homo`.
- ``src/dapi/src/lts/ls_homo.h`` — the 27-rule table (translated as
  :mod:`dectalk.lts.homo_table`).
- ``src/dapi/src/dic/dic_comm.c`` — homograph-field flags.
- ``src/dapi/src/include/fc_def.tab`` — the FC_* bits (translated as
  :mod:`dectalk.dic.form_class_bits`).
"""

from __future__ import annotations

from typing import Final

from dectalk.dic.form_class_bits import FC_ADV, FC_HOMOGRAPH, FC_NOUN
from dectalk.lts.homo_table import HomoRule, homo_table

BATS705_DEFAULT_FC: Final[int] = FC_NOUN
"""Mask assigned to a zero (unknown) previous word before the rule
loop runs — and written back into the context tracking, mirroring the
C's in-place ``fc_struct`` mutation (BATS#705, ls_homo.c line 371)."""


def select_homograph_entry(
    p_fc: int,
    s_fc: int,
    *,
    cur_fc: int = 0,
    prev_fc: int = 0,
    prev_prev_fc: int | None = None,
    first_word: bool = False,
) -> tuple[str, HomoRule | None]:
    """Pick ``"P"`` or ``"S"`` for a homograph pair from context masks.

    Args:
        p_fc: Built form-class mask of the primary (``P``) entry.
        s_fc: Built form-class mask of the secondary (``S``) entry.
        cur_fc: The current word's mask *before* the dictionary hit —
            zero for a plain dictionary word, the suffix rule's mask
            for a stripped derivation (``tears`` → ``-s`` →
            ``FC_NOUN|FC_VERB``). Gates the ``h_suffix`` rules.
        prev_fc: The previous word's tracked mask; pass 0 for an
            unknown word (the BATS#705 noun default applies — callers
            tracking context must persist :data:`BATS705_DEFAULT_FC`
            into their own state to mirror the C mutation).
        prev_prev_fc: The mask two words back, or ``None`` when the
            current word is not at least the sentence's third word
            (the C requires ``fc_index >= 3`` for the adverb
            fall-through).
        first_word: ``True`` when this is the sentence's first word —
            the C returns the primary entry outright.

    Returns:
        ``(reading, rule)`` where ``reading`` is ``"P"`` or ``"S"``
        and ``rule`` is the :class:`~dectalk.lts.homo_table.HomoRule`
        that decided it (``None`` for the first-word branch and the
        no-rule-fired default).
    """
    if first_word:
        return "P", None

    prev = prev_fc if prev_fc else BATS705_DEFAULT_FC

    for rule in homo_table:
        # h_suffix: every bit must be present in the current word's
        # pre-set mask (ls_homo.c line 390).
        if rule.h_suffix and (cur_fc & rule.h_suffix) != rule.h_suffix:
            continue
        # h_context: previous word, or the word before an adverb
        # (ls_homo.c lines 402-406).
        if rule.h_context:
            context_ok = bool(rule.h_context & prev)
            if not context_ok and prev_prev_fc is not None and (prev & FC_ADV):
                context_ok = bool(rule.h_context & prev_prev_fc)
            if not context_ok:
                continue
        if rule.h_select:
            if rule.h_select & p_fc:
                return "P", rule
            if rule.h_select & s_fc:
                return "S", rule
        if rule.h_elim:
            if rule.h_elim & s_fc:
                return "P", rule
            if rule.h_elim & p_fc:
                return "S", rule

    # No rule fired: the primary entry wins (C falls off the loop).
    return "P", None


def resolved_form_class(
    selected_fc: int,
    *,
    cur_fc: int = 0,
    rule: HomoRule | None = None,
) -> int:
    """Mask the homograph word exposes to *later* context checks.

    Mirrors the two write-back sites in the C:

    - ``ls_homo_homo``'s post-loop overwrite: when the deciding rule
      was suffix-gated, ``fc_struct`` takes the selected entry's mask
      (ls_homo.c line 489).
    - ``ls_dict_find_word``'s assignment: a zero ``fc_struct`` takes
      the selected entry's mask; a non-zero one (the suffix engine's
      mask) is kept and only ``FC_HOMOGRAPH`` is OR'd in
      (ls_dict.c lines 741-748).

    Args:
        selected_fc: Built mask of the entry the disambiguator chose.
        cur_fc: The current word's pre-hit mask (see
            :func:`select_homograph_entry`).
        rule: The rule returned by :func:`select_homograph_entry`.

    Returns:
        The mask to record for this word in the caller's context
        tracking.
    """
    if rule is not None and rule.h_suffix:
        return selected_fc
    if cur_fc == 0:
        return selected_fc
    return cur_fc | FC_HOMOGRAPH


__all__ = [
    "BATS705_DEFAULT_FC",
    "resolved_form_class",
    "select_homograph_entry",
]
