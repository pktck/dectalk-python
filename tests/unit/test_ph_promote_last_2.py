"""Verify promote_last_2 matches ph_aloph2.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FCBNEXT, FNOSTRESS, FSTRESS_1, FSTRESS_2
from dectalk.ph.promote_last_2 import promote_last_2


def _us(code: int | USPhoneme) -> int:
    """Build a font-encoded US phoneme code."""
    return (PFUSA << 8) | int(code)


def test_empty_state_returns_false() -> None:
    """A DphT with phonemes / sentstruc unset returns False."""
    state = DphT()
    assert promote_last_2(state, 0) is False


def test_no_secondary_stresses_returns_false() -> None:
    """When no FSTRESS_2 is set on a syllabic phoneme, no promotion."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 4
    state.sentstruc = [FNOSTRESS, FNOSTRESS, FCBNEXT, FNOSTRESS]
    state.nphonetot = 4
    assert promote_last_2(state, 0) is False


def test_secondary_stress_before_boundary_is_promoted() -> None:
    """A FSTRESS_2 in the span gets promoted to FSTRESS_1."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 4
    state.sentstruc = [FNOSTRESS, FSTRESS_2, FNOSTRESS, FCBNEXT]
    state.nphonetot = 4
    assert promote_last_2(state, 0) is True
    assert state.sentstruc[1] & FSTRESS_1
    assert not (state.sentstruc[1] & FSTRESS_2)


def test_only_last_secondary_stress_is_promoted() -> None:
    """When multiple secondary stresses exist, only the last gets promoted."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 5
    state.sentstruc = [
        FNOSTRESS,
        FSTRESS_2,  # First secondary — won't be promoted.
        FNOSTRESS,
        FSTRESS_2,  # Last secondary — this one gets promoted.
        FCBNEXT,
    ]
    state.nphonetot = 5
    assert promote_last_2(state, 0) is True
    # Index 1 still has FSTRESS_2.
    assert state.sentstruc[1] & FSTRESS_2
    # Index 3 promoted to FSTRESS_1 and cleared of FSTRESS_2.
    assert state.sentstruc[3] & FSTRESS_1
    assert not (state.sentstruc[3] & FSTRESS_2)


def test_msym_zero_special_case_no_promotion() -> None:
    """The C source's ``done_it == 0`` gate means msym=0 can't be promoted.

    Specifically: if msym==0 and the very next syllable carries
    FSTRESS_2, ``done_it`` is set to ``m = 1`` (not 0), so a
    promotion will happen. But if there's no later FSTRESS_2, the
    gate returns False even if a boundary is hit.
    """
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY), _us(USPhoneme.IY)]
    state.sentstruc = [FSTRESS_2, FCBNEXT]
    state.nphonetot = 2
    # msym=0 is skipped for the secondary-stress check, so the only
    # secondary stress (at index 0) doesn't get recorded.
    assert promote_last_2(state, 0) is False
    assert state.sentstruc[0] & FSTRESS_2  # Unchanged.


def test_no_boundary_no_promotion() -> None:
    """If no boundary is reached, no promotion happens (even with FSTRESS_2)."""
    state = DphT()
    state.phonemes = [_us(USPhoneme.IY)] * 3
    state.sentstruc = [FNOSTRESS, FSTRESS_2, FNOSTRESS]
    state.nphonetot = 3
    assert promote_last_2(state, 0) is False
    # FSTRESS_2 unchanged.
    assert state.sentstruc[1] & FSTRESS_2
