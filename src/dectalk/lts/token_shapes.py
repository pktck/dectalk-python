"""Alphanumeric-cluster segmentation + contextual roman numerals.

Two token *shapes* the C front end recognises in its NWS (non-white-space)
text pre-processor, ported here as chunk-loop helpers for
:func:`dectalk.api.speak.text_to_dectalk_phonemes` (issues #323 / #324).
Both live in ``src/dapi/src/cmd/par_rule.par`` — the compiled rule table
the CMD interpreter (``par_pars.c``) runs *before* the LTS front end ever
sees a token — not in ``ls_task.c``.

Mixed alphanumeric clusters (issue #323)
----------------------------------------
``par_rule.par`` rules R390/R391 insert a space at every digit-letter
boundary, so ``A1`` → ``A 1``, ``3M`` → ``3 M``, ``B2B`` → ``B 2 B``,
``42kg`` → ``42 kg``, ``1E10`` → ``1 E 10``, ``6.02e23`` → ``6.02 e 23``.
Guard rule R389 (``D<+>S{st,s,nd,rd,th}<1>``) protects ordinal/plural
suffixes so ``1st`` / ``42nd`` / ``1990s`` / ``70s`` are *not* split —
those stay with the numeric dispatch in
:mod:`dectalk.lts.numeric_formats`. Each split run is then re-processed
as an independent word by the normal pipeline:

- digit runs read as numbers (``42`` → "forty two", ``10`` → "ten");
- letter runs pronounce via LTS when pronounceable (``cat`` → "cat",
  single ``A`` → the article schwa, ``M`` → "em") and spell
  letter-by-letter when they are an unpronounceable all-caps cluster
  (``kg`` → "kay gee") — exactly the C ``ls_spel_say_it``
  (``l_us_sp1.c:61``) decision, reused here via
  :func:`dectalk.lts.spell_or_say.say_it`.

:func:`split_alnum_runs` produces the runs; :func:`spell_form` upper-cases
the runs the say-it predicate would spell so the chunk loop's existing
all-caps path renders them. ``'.'`` binds to the surrounding digit run so
the decimal in ``6.02e23`` survives (``6.02`` | ``e`` | ``23``).

Contextual roman numerals (issue #324)
--------------------------------------
``par_rule.par`` rule R387 —
``U<1>A<+>W<+>h/roman_num,U<1-5>/r/$7/$9/|FAIL/`` — rewrites a roman
numeral to its ordinal value *only* when it directly follows a
capitalised word: ``Chapter IV`` → ``Chapter the 4th`` → "chapter the
fourth", ``Henry VIII`` → "Henry the eighth". The ``roman_num``
dictionary (``par_rule.par:934``) is a literal string table for the
values 2..20; ``I`` / ``V`` / ``X`` are deliberately commented out ("don't
support I to avoid the trouble"), so single-letter numerals never
convert. There is *no* value evaluator and *no* cardinal path.

The capitalised-word prefix is the whole guard: bare ``IV`` (no preceding
word), lowercase ``iv``, ``chapter IV`` (lowercase carrier), and
``Chapter, IV`` (punctuation, not whitespace, before the numeral) all
fail R387 and pass through untouched — the numeral is then read as an
ordinary word. Real words like ``mix`` / ``did`` / ``civil`` never match:
they are lowercase and absent from the exact-string table.
:func:`roman_ordinal_text` returns the ``the Nth`` rewrite for a table
hit; :func:`is_clean_cap_word` tests the preceding chunk.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.spell_or_say import say_it

# ``roman_num`` dictionary (par_rule.par:934-955): the literal roman
# strings the C rule recognises, mapped to their integer value. Values
# 2..20 only; I(1)/V(5)/X(10) are commented out in the C source, so every
# recognised numeral is at least two letters.
ROMAN_ORDINALS: Final[dict[str, int]] = {
    "II": 2,
    "III": 3,
    "IV": 4,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
}

_MIN_SPELL_RUN: Final[int] = 2
"""Single letters keep their original case; the say-it spell decision only
applies to 2+-letter clusters (``ls_spel_say_it`` spells nothing shorter)."""


def _ordinal_text(value: int) -> str:
    """``4`` → ``4th``, ``2`` → ``2nd`` (the ``$9`` dictionary value form)."""
    is_teen = 10 <= value % 100 <= 20  # noqa: PLR2004 — 11th..20th all take "th"
    suffix = "th" if is_teen else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def roman_ordinal_text(token: str) -> str | None:
    """``the Nth`` rewrite for a roman numeral in the C table, else ``None``.

    ``token`` must be the exact (upper-case) numeral text; membership is an
    exact-string lookup, so only the 2..20 entries convert.
    """
    value = ROMAN_ORDINALS.get(token)
    if value is None:
        return None
    return f"the {_ordinal_text(value)}"


def is_clean_cap_word(chunk: str | None) -> bool:
    """True when ``chunk`` is R387's ``U<1>A<+>`` capitalised-word prefix.

    The C pattern requires an upper-case first letter followed by one or
    more letters, then *whitespace* immediately before the numeral — so the
    word must carry no trailing punctuation (``Chapter,`` fails). Leading
    punctuation is ignored (the rule matches ``Chapter`` inside
    ``(Chapter``).
    """
    if not chunk:
        return False
    stripped = chunk.lstrip("\"'([{<")
    return (
        len(stripped) >= _MIN_SPELL_RUN
        and stripped.isascii()
        and stripped.isalpha()
        and stripped[0].isupper()
    )


def is_mixed_alnum(token: str) -> bool:
    """True when ``token`` mixes letters and digits (an R390/R391 split site).

    Restricted to ASCII ``[A-Za-z0-9.]`` with at least one letter *and* one
    digit; other punctuation is owned by the symbol/numeric lanes, and
    non-ASCII chunks fall through (the C library's Latin-1 handling is a
    separate question).
    """
    if not token.isascii():
        return False
    has_alpha = has_digit = False
    for ch in token:
        if ch.isalpha():
            has_alpha = True
        elif ch.isdigit() or ch == ".":
            has_digit = has_digit or ch.isdigit()
        else:
            return False
    return has_alpha and has_digit


def split_alnum_runs(token: str) -> list[str]:
    """Split ``token`` into maximal letter / digit runs (R390/R391).

    ``'.'`` binds to the digit run it sits in so decimals survive:
    ``6.02e23`` → ``["6.02", "e", "23"]``. ``A1`` → ``["A", "1"]``,
    ``B2B`` → ``["B", "2", "B"]``, ``42kg`` → ``["42", "kg"]``.
    """
    runs: list[str] = []
    buf: list[str] = []
    mode: str | None = None  # "a" (alpha) or "d" (digit/decimal)
    for ch in token:
        this = "a" if ch.isalpha() else "d"
        if mode is not None and this != mode and buf:
            runs.append("".join(buf))
            buf = []
        buf.append(ch)
        mode = this
    if buf:
        runs.append("".join(buf))
    return runs


def spell_form(run: str) -> str:
    """Upper-case a letter run the say-it predicate would spell, else pass it.

    Upper-casing routes the run through the chunk loop's existing all-caps
    ``say_it`` spelling path (``kg`` → ``KG`` → "kay gee"). Pronounceable
    runs (``cat``), single letters, and digit runs are returned unchanged so
    the normal word pipeline handles them.
    """
    if len(run) >= _MIN_SPELL_RUN and run.isalpha() and not say_it(run.upper()):
        return run.upper()
    return run


__all__ = [
    "ROMAN_ORDINALS",
    "is_clean_cap_word",
    "is_mixed_alnum",
    "roman_ordinal_text",
    "spell_form",
    "split_alnum_runs",
]
