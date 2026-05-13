"""Verify make_phone / add_feature match ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import HAT_F0_SIZES_SPECIFIED
from dectalk.ph.make_phone import add_feature, make_phone
from dectalk.ph.numeric_constants import NPHON_MAX


def test_make_phone_appends_triple() -> None:
    """First call writes index 0 and bumps nphonetot."""
    state = DphT()
    make_phone(state, int(USPhoneme.IY), 0, 50, 200)
    assert state.phonemes is not None
    assert state.phonemes[0] == int(USPhoneme.IY)
    assert state.user_durs is not None
    assert state.user_durs[0] == 50
    assert state.user_f0 is not None
    assert state.user_f0[0] == 200
    assert state.nphonetot == 1


def test_make_phone_guards_on_nphonetot_ahead_of_n() -> None:
    """When nphonetot > n, no write happens (safety guard)."""
    state = DphT()
    state.nphonetot = 5
    state.phonemes = [99] * 10
    make_phone(state, int(USPhoneme.IY), 0, 50, 200)
    # No append: nphonetot stays at 5 and phonemes[5] still 99.
    assert state.nphonetot == 5
    assert state.phonemes[5] == 99


def test_make_phone_skips_user_f0_when_hat_f0_sizes_specified() -> None:
    """When f0mode == HAT_F0_SIZES_SPECIFIED, user_f0 isn't written."""
    state = DphT()
    state.f0mode = HAT_F0_SIZES_SPECIFIED
    make_phone(state, int(USPhoneme.IY), 0, 50, 999)
    assert state.user_f0 is not None
    assert state.user_f0[0] == 0  # unwritten, default 0.


def test_make_phone_caps_at_nphon_max() -> None:
    """nphonetot doesn't exceed NPHON_MAX."""
    state = DphT()
    state.nphonetot = NPHON_MAX
    # n needs to be >= nphonetot to pass the guard.
    make_phone(state, int(USPhoneme.IY), NPHON_MAX, 50, 200)
    # nphonetot stays at NPHON_MAX (no increment past).
    assert state.nphonetot == NPHON_MAX


def test_add_feature_ors_mask() -> None:
    """``add_feature`` ORs the mask into sentstruc[location]."""
    state = DphT()
    add_feature(state, 0x04, 3)
    assert state.sentstruc is not None
    assert state.sentstruc[3] == 0x04
    add_feature(state, 0x02, 3)
    assert state.sentstruc[3] == 0x06


def test_add_feature_rejects_out_of_range_location() -> None:
    """Locations < 0 or >= NPHON_MAX are silently ignored."""
    state = DphT()
    add_feature(state, 0x01, -1)
    add_feature(state, 0x01, NPHON_MAX)
    # sentstruc never grew (no writes).
    assert state.sentstruc is None or all(b == 0 for b in state.sentstruc)


def test_add_feature_rejects_invalid_feaname() -> None:
    """feaname <= 0 or too large is silently ignored."""
    state = DphT()
    add_feature(state, 0, 0)  # feaname == 0
    add_feature(state, -1, 0)  # feaname < 0
    assert state.sentstruc is None or all(b == 0 for b in state.sentstruc)
