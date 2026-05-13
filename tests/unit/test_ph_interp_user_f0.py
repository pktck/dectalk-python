"""Verify interp_user_f0 matches ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import HAT_FALL, HAT_RISE, S1, SEMPH, USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.interp_user_f0 import interp_user_f0
from dectalk.ph.inton_constants import (
    HAT_F0_SIZES_SPECIFIED,
    PHONE_TARGETS_SPECIFIED,
    SINGING,
)


def test_s1_with_f0_bumps_by_1000() -> None:
    """A ``S1`` symbol with f0=100 emits user_f0=1100, mode=HAT_F0_SIZES."""
    state = DphT()
    curr_dur = [50]
    curr_f0 = [100]
    mf0 = [0]
    interp_user_f0(state, curr_dur, curr_f0, S1, mf0)
    assert state.user_f0 is not None
    assert state.user_f0[0] == 1100
    assert state.user_offset is not None
    assert state.user_offset[0] == 50
    assert state.f0mode == HAT_F0_SIZES_SPECIFIED
    assert mf0[0] == 1
    # Pointer scratch cleared.
    assert curr_f0[0] == 0
    assert curr_dur[0] == 0


def test_hat_rise_bumps_by_200() -> None:
    """A HAT_RISE with f0=50 emits user_f0=250."""
    state = DphT()
    curr_dur = [0]
    curr_f0 = [50]
    mf0 = [0]
    interp_user_f0(state, curr_dur, curr_f0, HAT_RISE, mf0)
    assert state.user_f0 is not None
    assert state.user_f0[0] == 250


def test_hat_fall_bumps_by_400() -> None:
    """A HAT_FALL with f0=50 emits user_f0=450."""
    state = DphT()
    curr_dur = [0]
    curr_f0 = [50]
    mf0 = [0]
    interp_user_f0(state, curr_dur, curr_f0, HAT_FALL, mf0)
    assert state.user_f0 is not None
    assert state.user_f0[0] == 450


def test_negative_f0_negated() -> None:
    """Negative f0 inputs are negated (made absolute)."""
    state = DphT()
    curr_f0 = [-50]
    interp_user_f0(state, [0], curr_f0, S1, [0])
    assert state.user_f0 is not None
    assert state.user_f0[0] == 1050


def test_f0_clamped_to_199() -> None:
    """f0 values above 199 are clamped to 199."""
    state = DphT()
    curr_f0 = [500]
    interp_user_f0(state, [0], curr_f0, S1, [0])
    assert state.user_f0 is not None
    assert state.user_f0[0] == 1199


def test_low_f0_with_non_stress_sym_sets_singing() -> None:
    """A non-stress symbol with f0%1000 <= 37 switches to SINGING."""
    state = DphT()
    curr_f0 = [30]  # Below 37 → singing.
    interp_user_f0(state, [0], curr_f0, int(USPhoneme.IY), [0])
    assert state.f0mode == SINGING


def test_high_f0_with_non_stress_sym_sets_phone_targets() -> None:
    """A non-stress symbol with f0%1000 > 37 switches to PHONE_TARGETS."""
    state = DphT()
    curr_f0 = [100]
    interp_user_f0(state, [0], curr_f0, int(USPhoneme.IY), [0])
    assert state.f0mode == PHONE_TARGETS_SPECIFIED


def test_zero_f0_with_stress_sym_just_bumps_mf0() -> None:
    """Stress sym with f0=0 (and not HAT_F0_SIZES yet) only bumps mf0."""
    state = DphT()
    curr_dur = [10]
    curr_f0 = [0]
    mf0 = [5]
    interp_user_f0(state, curr_dur, curr_f0, SEMPH, mf0)
    assert mf0[0] == 6
    assert state.f0mode == 0  # Unchanged.


def test_phone_targets_mode_skips_stress_path() -> None:
    """When f0mode is already PHONE_TARGETS, stress symbols go to else branch."""
    state = DphT()
    state.f0mode = PHONE_TARGETS_SPECIFIED
    curr_f0 = [100]
    interp_user_f0(state, [0], curr_f0, S1, [0])
    # The "is_hat_or_stress" condition guards against PHONE_TARGETS,
    # so we hit the else branch — but it's an error case (mixing), so
    # f0mode stays PHONE_TARGETS_SPECIFIED.
    assert state.f0mode == PHONE_TARGETS_SPECIFIED
