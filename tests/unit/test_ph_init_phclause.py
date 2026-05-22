"""Verify init_phclause zeroes per-clause arrays and seeds window pointers.

These tests enforce the field-by-field audit performed in issue #74:
``init_phclause`` zeroes **exactly** five arrays and two scalars, and
seeds five window-pointer aliases. Every other ``DphT`` field is left
untouched. The C source (``src/dapi/src/ph/ph_claus.c`` lines 575-612)
is the authoritative spec; the audit table in
``src/dectalk/ph/init_phclause.py`` documents the mapping.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.init_phclause import init_phclause
from dectalk.ph.inton_constants import SAFETY
from dectalk.ph.numeric_constants import NPHON_MAX

_BUF_SIZE = NPHON_MAX + SAFETY + 2


# ---------------------------------------------------------------------------
# Existing invariants (kept verbatim — these are the smoke checks).
# ---------------------------------------------------------------------------


def test_arrays_are_sized_to_buffer() -> None:
    """All 5 per-clause arrays are resized to ``NPHON_MAX + SAFETY + 2``."""
    state = DphT()
    init_phclause(state)
    for name in ("allophons", "allofeats", "allodurs", "f0tar", "f0tim"):
        assert len(getattr(state, name)) == _BUF_SIZE


def test_arrays_are_zeroed() -> None:
    """Every element of every per-clause array is 0."""
    state = DphT()
    init_phclause(state)
    for name in ("allophons", "allofeats", "allodurs", "f0tar", "f0tim"):
        assert all(v == 0 for v in getattr(state, name))


def test_scalar_resets() -> None:
    """``fvvtran`` / ``bvvtran`` are reset to 0."""
    state = DphT(fvvtran=5, bvvtran=7)
    init_phclause(state)
    assert state.fvvtran == 0
    assert state.bvvtran == 0


def test_window_pointers_alias_parent_arrays() -> None:
    """The 5 window-pointer fields alias their parent arrays."""
    state = DphT()
    init_phclause(state)
    assert state.phonemes is state.allophons
    assert state.sentstruc is state.allofeats
    assert state.user_durs is state.allodurs
    assert state.user_f0 is state.f0tar
    assert state.user_offset is state.f0tim


def test_writing_via_window_pointer_visible_in_parent() -> None:
    """Mutating a window-pointer slot is visible in the parent array."""
    state = DphT()
    init_phclause(state)
    assert state.phonemes is not None
    state.phonemes[10] = 42
    assert state.allophons[10] == 42


def test_idempotent_reinit() -> None:
    """Calling ``init_phclause`` twice leaves everything zeroed."""
    state = DphT()
    init_phclause(state)
    assert state.allophons is not None
    state.allophons[0] = 99
    init_phclause(state)
    assert state.allophons[0] == 0


# ---------------------------------------------------------------------------
# Audit invariants added for issue #74 — what init_phclause MUST NOT touch.
# ---------------------------------------------------------------------------


def test_alloopenq_not_touched() -> None:
    """``alloopenq`` is NOT in the C zeroing loop — must be left as-is.

    C source ``ph_claus.c`` line 578-589 zeroes only
    ``allophons``/``allofeats``/``allodurs``/``f0tar``/``f0tim``. The
    ``alloopenq`` array is *intentionally* untouched per clause: it
    gets fully rewritten during phoneme processing.
    """
    state = DphT()
    state.alloopenq = [11, 22, 33, 44, 55]
    init_phclause(state)
    assert state.alloopenq == [11, 22, 33, 44, 55]


def test_symbols_not_touched() -> None:
    """``symbols`` is parsed-input data — init_phclause must not clear it."""
    state = DphT()
    state.symbols = [7, 8, 9]
    state.nsymbtot = 3
    init_phclause(state)
    assert state.symbols == [7, 8, 9]
    assert state.nsymbtot == 3


def test_wordclass_not_touched() -> None:
    """``wordclass`` is written by the front-end — init_phclause leaves it."""
    state = DphT()
    state.wordclass = [0x1234, 0x5678]
    state.holdwordclass = 0xCAFE
    init_phclause(state)
    assert state.wordclass == [0x1234, 0x5678]
    assert state.holdwordclass == 0xCAFE


def test_nallotot_nphonetot_not_touched() -> None:
    """Phoneme counters are upstream-owned, not part of the per-clause reset."""
    state = DphT()
    state.nallotot = 17
    state.nphonetot = 23
    init_phclause(state)
    assert state.nallotot == 17
    assert state.nphonetot == 23


def test_voice_and_speaker_scalars_preserved() -> None:
    """Voice / speaker / timing scalars survive a clause boundary.

    These are set during phinit / voice loading and must persist for
    every clause spoken with the same speaker. ``init_phclause`` only
    resets ``fvvtran`` and ``bvvtran``.
    """
    state = DphT()
    # Pick a representative cross-section of scalars that get set during
    # speaker init and would break audio if reset per-clause.
    state.f0_lp_filter = 2100
    state.f0minimum = 880
    state.f0scalefac = 4100
    state.fnscale = 12345
    state.malfem = 1
    state.tcum = -1
    state.nphone = 42
    state.last_lang = 7
    state.assertiveness = 100
    state.spdefb1off = 50
    state.f0_dep_tilt = 33
    init_phclause(state)
    assert state.f0_lp_filter == 2100
    assert state.f0minimum == 880
    assert state.f0scalefac == 4100
    assert state.fnscale == 12345
    assert state.malfem == 1
    assert state.tcum == -1
    assert state.nphone == 42
    assert state.last_lang == 7
    assert state.assertiveness == 100
    assert state.spdefb1off == 50
    assert state.f0_dep_tilt == 33


def test_fconsfeats_not_touched_in_english_build() -> None:
    """``fconsfeats`` is FRENCH-only — leave untouched in the default build.

    The Python port doesn't build for FRENCH, so the
    ``pDph_t->fconsfeats[i] = 0;`` line inside the ``#ifdef FRENCH``
    block must not execute. The Python implementation correctly skips it.
    """
    state = DphT()
    state.fconsfeats = [1, 2, 3]
    init_phclause(state)
    assert state.fconsfeats == [1, 2, 3]


def test_new_sentence_not_touched_in_english_build() -> None:
    """``new_sentence`` is GERMAN-only — leave untouched in the default build.

    C source line 608 sets ``pDph_t->new_sentence = TRUE`` only under
    ``#ifdef GERMAN``. The Python port doesn't build for GERMAN, so
    this scalar must keep its pre-call value.
    """
    state = DphT()
    state.new_sentence = 99
    init_phclause(state)
    assert state.new_sentence == 99


def test_pstphsettar_handle_preserved() -> None:
    """The PHSETTAR sub-struct handle is created during init, not per clause.

    ``pSTphsettar`` is allocated once (via calloc in C, via assignment
    in Python) and threaded through phsettar. Resetting it per clause
    would lose the initsw-state flag that suppresses double-init.
    """
    state = DphT()
    sentinel = object()
    state.pSTphsettar = sentinel
    init_phclause(state)
    assert state.pSTphsettar is sentinel


def test_pre_existing_array_contents_fully_cleared() -> None:
    """A pre-populated buffer is fully overwritten (not truncated/extended).

    The C loop writes ``= 0`` to every index 0..(NPHON_MAX+SAFETY+1).
    Python reassigns ``[0] * _BUF_SIZE`` — equivalent for value, but
    we also assert the *length* is exactly ``_BUF_SIZE`` (no leftover
    tail from a previous, larger allocation, no truncated head).
    """
    state = DphT()
    # Pre-populate with non-zero scratch that's longer than the buffer.
    state.allophons = [1] * (_BUF_SIZE + 50)
    state.f0tar = [2] * (_BUF_SIZE - 3)
    init_phclause(state)
    assert len(state.allophons) == _BUF_SIZE
    assert len(state.f0tar) == _BUF_SIZE
    assert all(v == 0 for v in state.allophons)
    assert all(v == 0 for v in state.f0tar)


def test_window_pointer_index_zero_is_array_index_zero() -> None:
    """The Python port's window-pointer convention: no SAFETY offset.

    This is a *documented* divergence from C, where ``phonemes`` is
    ``&allophons[SAFETY]``. The Python port aliases the whole parent
    list at index 0, so ``phonemes[0] is allophons[0]``. This test
    enforces the no-offset convention against accidental drift back
    toward a SAFETY-offset slice.
    """
    state = DphT()
    init_phclause(state)
    assert state.phonemes is not None
    assert state.sentstruc is not None
    assert state.user_durs is not None
    assert state.user_f0 is not None
    assert state.user_offset is not None
    # All five window pointers should yield the same list identity at index 0.
    state.allophons[0] = 0xABCD
    assert state.phonemes[0] == 0xABCD
    state.allofeats[0] = 0x1234
    assert state.sentstruc[0] == 0x1234
    state.allodurs[0] = 50
    assert state.user_durs[0] == 50
    state.f0tar[0] = 100
    assert state.user_f0[0] == 100
    state.f0tim[0] = 200
    assert state.user_offset[0] == 200
