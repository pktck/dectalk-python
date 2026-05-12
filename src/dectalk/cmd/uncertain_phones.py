"""Newer-version phoneme-pair checker.

Translated from ``src/dapi/src/cmd/cm_phon.c``. The C library uses
this to skip warnings when text contains phoneme syntax that's
ambiguous between the old DECtalk allophone set and the modern one.

The 4 listed digraphs are phonemes whose interpretation changed
between DECtalk versions (e.g. ``rx``, ``re``, ``ll``, ``ly``):
:func:`check_uncertain_phones` returns ``True`` when the input pair
is one of them, ``False`` otherwise. Inputs are case-folded via the
parser's ``par_lower`` table (= :data:`dectalk.lts.char_features.ls_lower`)
before the comparison, so ``RX``, ``rX``, ``Rx``, ``rx`` all match.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_lower

# Phoneme pairs whose meaning shifted between DECtalk versions.
uncertain_phones: Final[tuple[tuple[int, int], ...]] = (
    (ord("r"), ord("x")),
    (ord("r"), ord("e")),
    (ord("l"), ord("l")),
    (ord("l"), ord("y")),
)


def check_uncertain_phones(ph1: int, ph2: int) -> bool:
    """Return True if ``(ph1, ph2)`` is one of the ambiguous digraphs.

    Translates ``check_uncertain_phones`` from cm_phon.c. The C version
    case-folds ASCII A-Z via ``par_lower[]`` (lower-case-only branch),
    leaving the high bytes untouched.

    Args:
        ph1: First phoneme byte (0..255).
        ph2: Second phoneme byte (0..255).

    Returns:
        ``True`` iff the pair (after ASCII-uppercase folding) appears
        in :data:`uncertain_phones`.
    """
    # The C source only folds bytes in [A..Z] = [0x41..0x5A].
    # Outside that range it leaves the byte unchanged (par_lower is
    # identity for non-A-Z bytes in the US locale).
    if ord("A") <= ph1 <= ord("Z"):
        ph1 = ls_lower[ph1]
    if ord("A") <= ph2 <= ord("Z"):
        ph2 = ls_lower[ph2]
    return (ph1, ph2) in uncertain_phones


__all__ = ["check_uncertain_phones", "uncertain_phones"]
