"""Verify make_out_phonol matches ph_aloph2.c."""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.spc_packet import SpcPacket
from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import HAT_F0_SIZES_SPECIFIED
from dectalk.ph.make_out_phonol import make_out_phonol


def test_appends_triple_to_empty_buffers() -> None:
    """First call writes index 0 and bumps nallotot to 1."""
    ksd = KsdT()
    dph = DphT()
    make_out_phonol(ksd, dph, 0, 42, 0xABCD, 100, 200)
    assert dph.allophons[0] == 42
    assert dph.allofeats[0] == 0xABCD
    assert dph.user_durs is not None
    assert dph.user_durs[0] == 100
    assert dph.user_f0 is not None
    assert dph.user_f0[0] == 200
    assert dph.nallotot == 1


def test_increments_nallotot() -> None:
    """Successive calls bump nallotot."""
    ksd = KsdT()
    dph = DphT()
    make_out_phonol(ksd, dph, 0, 1, 0, 0, 0)
    make_out_phonol(ksd, dph, 0, 2, 0, 0, 0)
    make_out_phonol(ksd, dph, 0, 3, 0, 0, 0)
    assert dph.nallotot == 3
    assert dph.allophons[:3] == [1, 2, 3]


def test_hat_f0_sizes_specified_skips_user_f0() -> None:
    """When f0mode == HAT_F0_SIZES_SPECIFIED, user_f0 isn't written."""
    ksd = KsdT()
    dph = DphT()
    dph.f0mode = HAT_F0_SIZES_SPECIFIED
    make_out_phonol(ksd, dph, 0, 1, 0, 0, 999)
    # user_f0 was grown but the value is the default 0, not 999.
    assert dph.user_f0 is not None
    assert dph.user_f0[0] == 0


def test_defensive_margin_bails_out() -> None:
    """When nallotot > n + 8, the function bails out (no write, no bump)."""
    ksd = KsdT()
    dph = DphT()
    dph.nallotot = 20
    # n=10, so threshold is 18 — and nallotot=20 > 18 → bail out.
    make_out_phonol(ksd, dph, 10, 42, 0, 0, 0)
    # nallotot stayed the same.
    assert dph.nallotot == 20


def test_updates_spc_chain_via_set_index_allo() -> None:
    """The SPC index chain is updated to point at the new allo position."""
    ksd = KsdT()
    pkt = SpcPacket()
    while len(pkt.data) < 7:
        pkt.data.append(0)
    pkt.data[4] = 5  # data[4] == nphone we'll pass.
    ksd.spc_pkt_save = pkt
    dph = DphT()
    dph.nallotot = 3
    make_out_phonol(ksd, dph, 5, 1, 0, 0, 0)
    # Before set_index_allo: data[5] == 0; after: data[5] == 3 (the nallotot
    # at call time).
    assert pkt.data[5] == 3


def test_caps_at_nphon_max() -> None:
    """When nallotot >= NPHON_MAX, the increment is silently dropped.

    But because the defensive-margin check (nallotot > n+8) fires first,
    we test by setting n high enough to bypass it.
    """
    ksd = KsdT()
    dph = DphT()
    # Make nallotot exactly NPHON_MAX-1 so it could increment once,
    # then call with n = NPHON_MAX-1 to bypass the +8 margin.
    from dectalk.ph.numeric_constants import NPHON_MAX  # noqa: PLC0415

    dph.nallotot = NPHON_MAX
    make_out_phonol(ksd, dph, NPHON_MAX, 1, 0, 0, 0)
    # nallotot stayed at NPHON_MAX (didn't grow past).
    assert dph.nallotot == NPHON_MAX
