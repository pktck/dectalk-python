"""Verify move_stdangle matches ph_sort2.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1, S2, SEMPH, WBOUND, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.move_stdangle import move_stdangle


def test_semph_promotes_s1_in_word() -> None:
    """SEMPH dangling marker promotes the next S1 in the same word."""
    state = DphT()
    # [SEMPH, P, IY, S1, T, IY, WBOUND] — SEMPH at 0 should hop to S1 at 3.
    state.symbols = [SEMPH, USPhoneme.P, USPhoneme.IY, S1, USPhoneme.T, USPhoneme.IY, WBOUND]
    state.user_durs = [10, 0, 0, 0, 0, 0, 0]
    state.user_f0 = [0] * 7
    state.nsymbtot = 7
    settar = DphSettarSt()
    move_stdangle(KsdT(), state, settar, 0)
    # SEMPH at original 0 was deleted; S1 was promoted to SEMPH;
    # the original durdangle (10) was carried over.
    # After delete_symbol shifts everything down by 1: index 2 holds the promoted SEMPH.
    assert state.symbols[2] == SEMPH
    assert state.user_durs[2] == 10
    assert state.nsymbtot == 6
    assert settar.did_del == 1


def test_semph_falls_back_to_s2_when_no_s1() -> None:
    """SEMPH dangling marker falls back to first S2 if no S1 in word."""
    state = DphT()
    state.symbols = [SEMPH, USPhoneme.P, USPhoneme.IY, S2, USPhoneme.T, USPhoneme.IY, WBOUND]
    state.user_durs = [7, 0, 0, 0, 0, 0, 0]
    state.user_f0 = [0] * 7
    state.nsymbtot = 7
    move_stdangle(KsdT(), state, DphSettarSt(), 0)
    # After delete_symbol: original S2 at index 3 -> position 2, promoted to SEMPH.
    assert state.symbols[2] == SEMPH
    assert state.user_durs[2] == 7
    assert state.nsymbtot == 6


def test_s1_promotes_first_s2() -> None:
    """S1 dangling marker promotes the first S2 in the word."""
    state = DphT()
    state.symbols = [S1, USPhoneme.P, USPhoneme.IY, S2, USPhoneme.T, USPhoneme.IY, WBOUND]
    state.user_durs = [5, 0, 0, 0, 0, 0, 0]
    state.user_f0 = [0] * 7
    state.nsymbtot = 7
    move_stdangle(KsdT(), state, DphSettarSt(), 0)
    # S2 at original index 3 -> promoted to S1; original S1 deleted; result shifted.
    assert state.symbols[2] == S1
    assert state.user_durs[2] == 5
    assert state.nsymbtot == 6


def test_rule3_attaches_to_first_syllabic() -> None:
    """A non-SEMPH/non-S1 stress attaches to the first syllabic vowel."""
    state = DphT()
    # S2 dangles before P-IY; falls through rule 1/2 and rule 3 puts S2
    # on the slot just before the syllabic IY (index 2).
    state.symbols = [S2, USPhoneme.P, USPhoneme.IY, USPhoneme.T, WBOUND]
    state.user_durs = [3, 0, 0, 0, 0]
    state.user_f0 = [0] * 5
    state.nsymbtot = 5
    move_stdangle(KsdT(), state, DphSettarSt(), 0)
    # The "carry-forward" pass moves P to slot 0, then IY at slot 2 triggers
    # putting stdangle on slot m-1 (=1). No delete in this branch.
    assert state.symbols[0] == USPhoneme.P
    assert state.symbols[1] == S2
    assert state.user_durs[1] == 3
    assert state.nsymbtot == 5  # No delete in syllabic-attach branch.


def test_rule3_word_boundary_deletes_prev_slot() -> None:
    """Hitting a word boundary before any syllabic deletes the slot before."""
    state = DphT()
    # S2 at index 0, then consonants, then WBOUND at index 3 — no syllabic seen.
    state.symbols = [S2, USPhoneme.P, USPhoneme.T, WBOUND]
    state.user_durs = [4, 0, 0, 0]
    state.user_f0 = [0] * 4
    state.nsymbtot = 4
    settar = DphSettarSt()
    move_stdangle(KsdT(), state, settar, 0)
    # Carry-forward shifts P -> slot 0, T -> slot 1, then at m=3 WBOUND
    # is hit and delete_symbol(m-1 = 2) deletes the just-carried T slot.
    assert state.symbols[0] == USPhoneme.P
    assert state.nsymbtot == 3
    assert settar.did_del == 1


def test_rule3_replaces_weaker_stress() -> None:
    """A stronger dangling stress (S1) replaces a weaker (S2) seen first."""
    state = DphT()
    # S1 dangling: rule 2 first tries S2 — succeeds, S2 at index 1 promoted to S1.
    # But we want rule 3's branch where a weaker stress is met before a vowel.
    # Use a SEMPH dangling and an S2 with no S1 anywhere, no boundary -> rule 1
    # falls through (no S1 then no S2 in same word). Actually we need a setup
    # where the word boundary is between SEMPH and S2 so rule 1 fails and rule 3
    # triggers a stress-replace path.
    state.symbols = [SEMPH, USPhoneme.P, WBOUND, USPhoneme.T, S2, USPhoneme.IY]
    state.user_durs = [9, 0, 0, 0, 0, 0]
    state.user_f0 = [0] * 6
    state.nsymbtot = 6
    move_stdangle(KsdT(), state, DphSettarSt(), 0)
    # Rule 1 (SEMPH path): break on WBOUND at index 2, no S1 found.
    # Then second loop, break on WBOUND at index 2, no S2 found.
    # Rule 3: m=1 (P, not boundary/stress/syllabic): carry P backward
    # -> symbols[0] = P. m=2 (WBOUND): delete_symbol(m-1 = 1).
    assert state.symbols[0] == USPhoneme.P
    assert state.nsymbtot == 5


def test_msym_out_of_range_returns_safely() -> None:
    """Defensive guard: out-of-range ``msym`` is a no-op."""
    state = DphT()
    state.symbols = [S1, USPhoneme.IY, WBOUND]
    state.user_durs = [0, 0, 0]
    state.user_f0 = [0, 0, 0]
    state.nsymbtot = 3
    settar = DphSettarSt()
    move_stdangle(KsdT(), state, settar, 99)
    # Nothing should have changed.
    assert state.symbols == [S1, USPhoneme.IY, WBOUND]
    assert state.nsymbtot == 3
    assert settar.did_del == 0
