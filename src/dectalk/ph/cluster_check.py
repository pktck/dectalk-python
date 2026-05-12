"""PH-side consonant-cluster legality check (font-encoded variant).

Translated from ``src/dapi/src/ph/p_us_sr1.c`` — the
``us_phcluster(f, s)`` function the PH stress-assignment pass uses
to decide whether a (first, second) consonant pair forms a legal
English onset cluster.

This is functionally the same logic as
:func:`dectalk.lts.cluster_check.ls_adju_cluster`, but operates on
**font-encoded** allophone codes (``(PFUSA << 8) | code``) rather
than raw codes — the PH side carries the full 16-bit font+code pair
through its pipeline.

Returns codes (defined locally in the C source):

- :data:`NOCLUSTER` (0) — no English onset
- :data:`CLUSTER` (1) — legal cluster
- :data:`CLUSTER_TRYS` (2) — legal *and* can absorb a leading /s/
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import PFUSA, USPhoneme

# Local PH-side cluster classification codes.
NOCLUSTER: Final[int] = 0
CLUSTER: Final[int] = 1
CLUSTER_TRYS: Final[int] = 2

# Font-encoded helpers (mirrors USP_X = (PFUSA << 8) | US_X from p_all_ph.h).
_FONT_SHIFT: Final[int] = 8


def _usp(code: USPhoneme) -> int:
    """Wrap a raw US allophone code as ``(PFUSA << 8) | code``."""
    return (PFUSA << _FONT_SHIFT) | int(code)


# Per-first-phoneme dispatch — same structure as the LTS-side rules
# but keyed on font-encoded phoneme codes.
_RULES: Final[dict[int, tuple[tuple[frozenset[int], int], ...]]] = {
    _usp(USPhoneme.P): ((frozenset({_usp(USPhoneme.LL), _usp(USPhoneme.R)}), CLUSTER_TRYS),),
    _usp(USPhoneme.B): ((frozenset({_usp(USPhoneme.LL), _usp(USPhoneme.R)}), CLUSTER),),
    _usp(USPhoneme.F): (
        (frozenset({_usp(USPhoneme.R)}), CLUSTER_TRYS),
        (frozenset({_usp(USPhoneme.LL)}), CLUSTER),
    ),
    _usp(USPhoneme.T): (
        (frozenset({_usp(USPhoneme.R)}), CLUSTER_TRYS),
        (frozenset({_usp(USPhoneme.W)}), CLUSTER),
    ),
    _usp(USPhoneme.D): ((frozenset({_usp(USPhoneme.R), _usp(USPhoneme.W)}), CLUSTER),),
    _usp(USPhoneme.TH): ((frozenset({_usp(USPhoneme.R), _usp(USPhoneme.W)}), CLUSTER),),
    _usp(USPhoneme.K): (
        (
            frozenset({_usp(USPhoneme.R), _usp(USPhoneme.LL), _usp(USPhoneme.W)}),
            CLUSTER_TRYS,
        ),
    ),
    _usp(USPhoneme.G): (
        (
            frozenset({_usp(USPhoneme.R), _usp(USPhoneme.LL), _usp(USPhoneme.W)}),
            CLUSTER,
        ),
    ),
    _usp(USPhoneme.S): (
        (
            frozenset(
                {
                    _usp(USPhoneme.W),
                    _usp(USPhoneme.LL),
                    _usp(USPhoneme.P),
                    _usp(USPhoneme.T),
                    _usp(USPhoneme.K),
                    _usp(USPhoneme.M),
                    _usp(USPhoneme.N),
                    _usp(USPhoneme.F),
                }
            ),
            CLUSTER,
        ),
    ),
    _usp(USPhoneme.SH): (
        (
            frozenset(
                {
                    _usp(USPhoneme.W),
                    _usp(USPhoneme.LL),
                    _usp(USPhoneme.P),
                    _usp(USPhoneme.T),
                    _usp(USPhoneme.R),
                    _usp(USPhoneme.M),
                    _usp(USPhoneme.N),
                }
            ),
            CLUSTER,
        ),
    ),
}


def us_phcluster(f: int, s: int) -> int:
    """Return :data:`NOCLUSTER` / :data:`CLUSTER` / :data:`CLUSTER_TRYS`.

    Faithful translation of ``us_phcluster(f, s)`` from
    ``src/dapi/src/ph/p_us_sr1.c``. The C function is a ``switch (f)``
    over the first font-encoded phoneme; for each case it scans a
    small set of acceptable second phonemes and returns the matching
    cluster code, falling through to NOCLUSTER.

    Args:
        f: First-phoneme font-encoded code (e.g. ``USP_P``).
        s: Second-phoneme font-encoded code.

    Returns:
        ``NOCLUSTER``, ``CLUSTER``, or ``CLUSTER_TRYS``.
    """
    rules = _RULES.get(f)
    if rules is None:
        return NOCLUSTER
    for second_set, code in rules:
        if s in second_set:
            return code
    return NOCLUSTER


__all__ = ["CLUSTER", "CLUSTER_TRYS", "NOCLUSTER", "us_phcluster"]
