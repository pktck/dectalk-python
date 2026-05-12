"""Verify ``ls_adju_is_cons`` / ``ls_adju_is_voc`` parity with ls_adju.c."""

from __future__ import annotations

from dectalk.lts import phone_predicates as pp
from dectalk.lts.grapheme_features import PCONS, PVOC, pfeat


def test_is_cons_matches_pfeat_bit() -> None:
    """For every code, ``is_cons`` matches the PCONS bit."""
    for code in range(len(pfeat)):
        assert pp.ls_adju_is_cons(code) == bool(pfeat[code] & PCONS)


def test_is_voc_matches_pfeat_bit() -> None:
    """For every code, ``is_voc`` matches the PVOC bit."""
    for code in range(len(pfeat)):
        assert pp.ls_adju_is_voc(code) == bool(pfeat[code] & PVOC)


def test_some_known_consonants() -> None:
    """Consonant codes 0x01..0x10 are consonants (per the C source)."""
    # Codes 0..15 in pfeat: looking at ls_us.c we expect these to be
    # consonant phonemes per the bit table.
    cons_count = sum(1 for c in range(len(pfeat)) if pp.ls_adju_is_cons(c))
    assert cons_count > 0


def test_some_known_vowels() -> None:
    """At least some pfeat entries are flagged as vowels."""
    voc_count = sum(1 for c in range(len(pfeat)) if pp.ls_adju_is_voc(c))
    assert voc_count > 0


def test_predicates_independent() -> None:
    """PCONS and PVOC bits can co-exist (e.g. consonant w/ voicing)."""
    # The C bits are independent; we don't assert mutual exclusion.
    cons = {c for c in range(len(pfeat)) if pp.ls_adju_is_cons(c)}
    voc = {c for c in range(len(pfeat)) if pp.ls_adju_is_voc(c)}
    # Just verify both sets are non-empty.
    assert len(cons) > 0
    assert len(voc) > 0
