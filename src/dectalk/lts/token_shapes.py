"""Alphanumeric-cluster segmentation for the tokenizer (issue #323).

A token *shape* the C front end recognises in its NWS (non-white-space)
text pre-processor, ported here as chunk-loop helpers for
:func:`dectalk.api.speak.text_to_dectalk_phonemes`. It lives in
``src/dapi/src/cmd/par_rule.par`` — the compiled rule table the CMD
interpreter (``par_pars.c``) runs *before* the LTS front end ever sees a
token — not in ``ls_task.c``.

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
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.spell_or_say import say_it

_MIN_SPELL_RUN: Final[int] = 2
"""Single letters keep their original case; the say-it spell decision only
applies to 2+-letter clusters (``ls_spel_say_it`` spells nothing shorter)."""


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
    "is_mixed_alnum",
    "spell_form",
    "split_alnum_runs",
]
