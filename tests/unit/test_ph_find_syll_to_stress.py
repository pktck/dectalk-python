"""Verify find_syll_to_stress matches ph_sort2.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import PFUSA, S1, S2, WBOUND, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english, LANG_german
from dectalk.ph.dph_t import DphT
from dectalk.ph.find_syll_to_stress import find_syll_to_stress


def _us(code: int | USPhoneme) -> int:
    """Build a font-encoded US phoneme code."""
    return (PFUSA << 8) | int(code)


def test_promotes_last_secondary_stress_to_primary() -> None:
    """Pass 1: a backward scan finds the last S2 and promotes to S1."""
    state = DphT()
    # symbols: [WBOUND, IY, S2, IY] — scanning backward from index 3.
    state.symbols = [WBOUND, _us(USPhoneme.IY), S2, _us(USPhoneme.IY)]
    state.nsymbtot = 4
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [4]
    find_syll_to_stress(ksd, state, locend, 0)
    # S2 is promoted to S1 and locend is unchanged (no insertion).
    assert state.symbols[2] == S1
    assert locend[0] == 4
    assert state.nsymbtot == 4


def test_promotes_only_most_recent_s2_when_multiple_present() -> None:
    """The backward walk returns on the *first* S2 it finds."""
    state = DphT()
    state.symbols = [WBOUND, S2, _us(USPhoneme.IY), S2, _us(USPhoneme.AA)]
    state.nsymbtot = 5
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [5]
    find_syll_to_stress(ksd, state, locend, 0)
    # The S2 at index 3 (later one) is promoted, the earlier S2 is left.
    assert state.symbols[3] == S1
    assert state.symbols[1] == S2
    assert locend[0] == 5


def test_german_skips_s2_promotion_pass() -> None:
    """For LANG_german, the first backward pass is skipped entirely.

    The C source's ``if (pKsd_t->lang_curr != LANG_german)`` gate
    means German clauses fall straight to Pass 2 (find the last
    word's first vowel and prepend ``S1``).
    """
    state = DphT()
    # symbols: [WBOUND, IY, S2, AA] — the S2 must NOT be promoted in German.
    # Instead Pass 2 inserts S1 before the last vowel (AA at index 3).
    state.symbols = [WBOUND, _us(USPhoneme.IY), S2, _us(USPhoneme.AA), 0, 0]
    state.nsymbtot = 4
    state.user_durs = [0, 0, 0, 0, 0, 0]
    state.user_f0 = [0, 0, 0, 0, 0, 0]
    ksd = KsdT()
    ksd.lang_curr = LANG_german
    locend = [4]
    find_syll_to_stress(ksd, state, locend, 0)
    # The S2 was not promoted to S1 (it shifted right by 1 due to insertion
    # before the final vowel, but its value is still S2).
    # Backward >= WBOUND scan: index 3 is font-encoded AA (>= WBOUND) → locbeg=3.
    # Forward scan from 3: AA is syllabic → insertphone(S1) at index 3.
    assert state.symbols[3] == S1
    assert state.symbols[4] == _us(USPhoneme.AA)
    # S2 at index 2 is unchanged (was never promoted).
    assert state.symbols[2] == S2
    assert locend[0] == 5


def test_inserts_s1_before_first_vowel_when_no_s2_found() -> None:
    """Pass 2: when no S2 exists, walk back to WBOUND then insert S1 before the next vowel."""
    state = DphT()
    # symbols: [WBOUND, IY, AA] — no S2. Walking back from index 2, the first
    # symbol >= WBOUND is index 2 (font-encoded AA, which is >= WBOUND).
    # Forward scan from index 2 finds AA (a vowel) → insertphone(S1) at index 2.
    state.symbols = [WBOUND, _us(USPhoneme.IY), _us(USPhoneme.AA), 0, 0]
    state.nsymbtot = 3
    state.user_durs = [0, 0, 0, 0, 0]
    state.user_f0 = [0, 0, 0, 0, 0]
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [3]
    find_syll_to_stress(ksd, state, locend, 0)
    # An S1 is inserted at index 2 (just before the AA), pushing AA to index 3.
    assert state.symbols[2] == S1
    assert state.symbols[3] == _us(USPhoneme.AA)
    # locend is incremented to track the shift.
    assert locend[0] == 4
    # nsymbtot grew by 1.
    assert state.nsymbtot == 4


def test_no_s2_no_vowel_falls_through_silently() -> None:
    """If no S2 and no syllabic phoneme in [locbeg, *locend), give up.

    Uses only non-syllabic consonants (K, T) for the post-WBOUND
    span so the forward Pass-2 scan finds nothing to stress.
    """
    state = DphT()
    state.symbols = [WBOUND, _us(USPhoneme.K), _us(USPhoneme.T), 0]
    state.nsymbtot = 3
    state.user_durs = [0, 0, 0, 0]
    state.user_f0 = [0, 0, 0, 0]
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [3]
    find_syll_to_stress(ksd, state, locend, 0)
    # Backward scan finds T (font-encoded, > WBOUND) at index 2 → locbeg=2.
    # Forward scan from 2 to <3: only T (non-syllabic) → no insert.
    assert state.symbols[:3] == [WBOUND, _us(USPhoneme.K), _us(USPhoneme.T)]
    assert locend[0] == 3
    assert state.nsymbtot == 3


def test_nstartphrase_bounds_backward_scan() -> None:
    """The backward S2 walk stops when m < nstartphrase."""
    state = DphT()
    # S2 sits at index 0, but nstartphrase=2 → backward walk never reaches it.
    state.symbols = [S2, _us(USPhoneme.IY), WBOUND, _us(USPhoneme.AA)]
    state.nsymbtot = 4
    state.user_durs = [0, 0, 0, 0, 0]
    state.user_f0 = [0, 0, 0, 0, 0]
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [4]
    # Backward scan only walks indices 3, 2 — neither is S2.
    # Then backward WBOUND scan finds WBOUND at index 2 → locbeg=2.
    # Forward scan from 2 to <4 finds AA at index 3 → insert S1 at 3.
    find_syll_to_stress(ksd, state, locend, 2)
    # The early-S2 at index 0 is untouched.
    assert state.symbols[0] == S2
    # S1 was inserted at index 3, pushing AA to index 4.
    assert state.symbols[3] == S1
    assert state.symbols[4] == _us(USPhoneme.AA)
    assert locend[0] == 5


def test_locend_at_zero_no_op() -> None:
    """If *locend = 0, both passes have an empty range and the function returns."""
    state = DphT()
    state.symbols = [WBOUND, _us(USPhoneme.IY)]
    state.nsymbtot = 2
    state.user_durs = [0, 0]
    state.user_f0 = [0, 0]
    ksd = KsdT()
    ksd.lang_curr = LANG_english
    locend = [0]
    find_syll_to_stress(ksd, state, locend, 0)
    # Nothing changed.
    assert locend[0] == 0
    assert state.symbols == [WBOUND, _us(USPhoneme.IY)]
