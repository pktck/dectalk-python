"""US English consonant-cluster legality check.

Translated from ``src/dapi/src/lts/l_us_ad1.c`` — the
``ls_adju_cluster(f, s)`` function used by the LTS adjustment pass
to decide whether a (first, second) consonant pair at the start of
a syllable forms a legal English onset cluster.

The function returns one of three codes:

- :data:`OK` (1) — legal cluster (e.g. "BL", "DR")
- :data:`TRYS` (2) — legal cluster *that could absorb a leading
  /s/ or /S/* (e.g. "PL" → "SPL" is also legal; "KR" → "SKR")
- :data:`ILLEGAL` (0) — no English onset starts with this pair

The legality table is hard-coded in the C source as a per-first-
phoneme ``switch`` block; we mirror that exactly with a small
dispatch dict so future allophone changes can be reviewed
side-by-side with the original.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import USPhoneme

# ls_defs.h cluster-classification codes.
ILLEGAL: Final[int] = 0
OK: Final[int] = 1
TRYS: Final[int] = 2


# Per-first-phoneme dispatch: (set_of_second_phonemes, return_code).
# Multiple rows per first-phoneme are tried in order; the first match
# wins. Mirrors the structure of the C ``switch`` block.
_CLUSTER_RULES: Final[dict[int, tuple[tuple[frozenset[int], int], ...]]] = {
    int(USPhoneme.P): ((frozenset({int(USPhoneme.LL), int(USPhoneme.R)}), TRYS),),
    int(USPhoneme.B): ((frozenset({int(USPhoneme.LL), int(USPhoneme.R)}), OK),),
    int(USPhoneme.F): (
        (frozenset({int(USPhoneme.R)}), TRYS),
        (frozenset({int(USPhoneme.LL)}), OK),
    ),
    int(USPhoneme.T): (
        (frozenset({int(USPhoneme.R)}), TRYS),
        (frozenset({int(USPhoneme.W)}), OK),
    ),
    int(USPhoneme.D): ((frozenset({int(USPhoneme.W), int(USPhoneme.R)}), OK),),
    int(USPhoneme.TH): ((frozenset({int(USPhoneme.W), int(USPhoneme.R)}), OK),),
    int(USPhoneme.K): (
        (
            frozenset({int(USPhoneme.W), int(USPhoneme.LL), int(USPhoneme.R)}),
            TRYS,
        ),
    ),
    int(USPhoneme.G): (
        (
            frozenset({int(USPhoneme.W), int(USPhoneme.LL), int(USPhoneme.R)}),
            OK,
        ),
    ),
    int(USPhoneme.S): (
        (
            frozenset(
                {
                    int(USPhoneme.W),
                    int(USPhoneme.LL),
                    int(USPhoneme.P),
                    int(USPhoneme.T),
                    int(USPhoneme.K),
                    int(USPhoneme.M),
                    int(USPhoneme.N),
                    int(USPhoneme.F),
                }
            ),
            OK,
        ),
    ),
    int(USPhoneme.SH): (
        (
            frozenset(
                {
                    int(USPhoneme.W),
                    int(USPhoneme.LL),
                    int(USPhoneme.R),
                    int(USPhoneme.P),
                    int(USPhoneme.T),
                    int(USPhoneme.M),
                    int(USPhoneme.N),
                }
            ),
            OK,
        ),
    ),
}


def ls_adju_cluster(f: int, s: int) -> int:
    """Return one of :data:`OK`, :data:`TRYS`, :data:`ILLEGAL` for the (f, s) onset.

    Translates ``ls_adju_cluster`` from
    ``src/dapi/src/lts/l_us_ad1.c`` line-for-line. The C version is a
    ``switch (f)`` over the first phoneme; for each case it scans a
    small set of acceptable second phonemes and returns the matching
    OK/TRYS code, or falls through to ILLEGAL.

    Args:
        f: First-phoneme allophone code (US_P, US_B, US_K, …).
        s: Second-phoneme allophone code.

    Returns:
        ILLEGAL (0), OK (1), or TRYS (2).
    """
    rules = _CLUSTER_RULES.get(f)
    if rules is None:
        return ILLEGAL
    for second_set, code in rules:
        if s in second_set:
            return code
    return ILLEGAL


__all__ = ["ILLEGAL", "OK", "TRYS", "ls_adju_cluster"]
