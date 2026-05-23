"""Unit tests for ``dectalk.vtm.resonator`` setup helpers."""

from __future__ import annotations

from dectalk.vtm.cosine_radius_tables import cosine_table, radius_table
from dectalk.vtm.frac import frac4mul
from dectalk.vtm.resonator import (
    NO_SAMPLE_RATE_CHANGE,
    SAMPLE_RATE_DECREASE,
    SAMPLE_RATE_INCREASE,
    d2pole_cf45,
    d2pole_cf123,
    d2pole_pf,
)


def _reference_abc(frequency: int, bandwidth: int, gain: int) -> tuple[int, int, int]:
    """Compute (a, b, c) the way the C source does, no Fs/2 zap."""
    radius = radius_table[bandwidth >> 3]
    bcoef = frac4mul(radius, cosine_table[frequency >> 3])
    ccoef = -frac4mul(radius, radius)
    temp = 4096 - bcoef - ccoef
    acoef = frac4mul(gain, temp) << 1
    return acoef, bcoef, ccoef


class TestD2PoleCf45:
    def test_in_band_matches_reference(self) -> None:
        a, b, c = d2pole_cf45(29722, NO_SAMPLE_RATE_CHANGE, 2000, 200, 4096)
        assert (a, b, c) == _reference_abc(2000, 200, 4096)

    def test_zaps_above_freq_cap(self) -> None:
        a, b, c = d2pole_cf45(29722, NO_SAMPLE_RATE_CHANGE, 4500, 200, 4096)
        # b=c=0, a = 4096 * 1.0 << 1 = 8192
        assert (a, b, c) == (8192, 0, 0)

    def test_zaps_above_bw_cap(self) -> None:
        a, b, c = d2pole_cf45(29722, NO_SAMPLE_RATE_CHANGE, 2000, 5000, 4096)
        assert b == 0
        assert c == 0

    def test_sample_rate_increase_scales_freq_bw(self) -> None:
        a1, b1, c1 = d2pole_cf45(29722, SAMPLE_RATE_INCREASE, 2200, 220, 4096)
        scaled_freq = (29722 * 2200) >> 15
        scaled_bw = (29722 * 220) >> 15
        assert (a1, b1, c1) == _reference_abc(scaled_freq, scaled_bw, 4096)


class TestD2PoleCf123:
    def test_in_band_matches_reference(self) -> None:
        a, b, c = d2pole_cf123(11025, 29722, NO_SAMPLE_RATE_CHANGE, 500, 50, 4096)
        assert (a, b, c) == _reference_abc(500, 50, 4096)

    def test_clamps_above_freq_cap(self) -> None:
        # F=5000 -> clamped to Fs/2 = 5512, BW to Fs/4 = 2756.
        a, b, c = d2pole_cf123(11025, 29722, NO_SAMPLE_RATE_CHANGE, 5000, 50, 4096)
        assert (a, b, c) == _reference_abc(5512, 2756, 4096)


class TestD2PolePf:
    def test_in_band_matches_reference(self) -> None:
        a, b, c = d2pole_pf(29722, NO_SAMPLE_RATE_CHANGE, 1500, 100, 4096)
        assert (a, b, c) == _reference_abc(1500, 100, 4096)

    def test_zap_returns_all_zero(self) -> None:
        assert d2pole_pf(29722, NO_SAMPLE_RATE_CHANGE, 4500, 100, 4096) == (0, 0, 0)
        assert d2pole_pf(29722, NO_SAMPLE_RATE_CHANGE, 1500, 5000, 4096) == (0, 0, 0)

    def test_decrease_vs_increase_differ(self) -> None:
        a_inc, _, _ = d2pole_pf(29722, SAMPLE_RATE_INCREASE, 2000, 200, 4096)
        a_dec, _, _ = d2pole_pf(29722, SAMPLE_RATE_DECREASE, 2000, 200, 4096)
        assert a_inc != a_dec
