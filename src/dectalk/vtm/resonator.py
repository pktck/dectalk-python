"""Resonator-coefficient setup helpers from vtmfunc.h.

Translated from ``src/dapi/src/vtm/vtmfunc.h`` lines 106-391. Three
near-identical functions converting ``(frequency, bandwidth, gain)``
to Q12 biquad coefficients ``(a, b, c)``:

- :func:`d2pole_cf45` — cascade F4/F5. Over-Fs/2 zaps b/c (DC pass).
- :func:`d2pole_cf123` — cascade F1/F2/F3. Over-Fs/2 clamps freq/bw
  to ``Fs/2`` / ``Fs/4``.
- :func:`d2pole_pf` — parallel formant. Over-Fs/2 zaps a/b/c (silent).

All three apply the same sample-rate scaling, read the precomputed
``cosine_table`` (``8192 * cos(2*pi*f*T)``) and ``radius_table``
(``4096 * exp(-pi*bw*T)``), and combine via :func:`frac4mul`.

The C functions return ``acoef`` and write ``bcoef`` / ``ccoef`` via
pointer; the Python translations collapse into a returned tuple.
"""

from __future__ import annotations

from dectalk.vtm.cosine_radius_tables import cosine_table, radius_table
from dectalk.vtm.frac import frac1mul, frac4mul

# Sample-rate-change enum values (vtminst.h lines 77-79).
SAMPLE_RATE_INCREASE = 0
SAMPLE_RATE_DECREASE = 1
NO_SAMPLE_RATE_CHANGE = 2

# 10/11 kHz formant-frequency / bandwidth caps. The active build
# always defines ``PC_SAMPLE_RATE == 11025`` so these apply.
_FREQ_CAP = 4500
_BW_CAP = 4950

__all__ = [
    "NO_SAMPLE_RATE_CHANGE",
    "SAMPLE_RATE_DECREASE",
    "SAMPLE_RATE_INCREASE",
    "d2pole_cf45",
    "d2pole_cf123",
    "d2pole_pf",
]


def _scale_freq_bw(
    frequency: int,
    bandwidth: int,
    inv_rate_scale: int,
    sample_rate_change: int,
) -> tuple[int, int]:
    """Apply sample-rate scaling to ``(frequency, bandwidth)``.

    Mirrors the leading ``switch`` block in all three ``d2pole_*``
    functions: DECREASE doubles the scaled values vs INCREASE.
    """
    if sample_rate_change == SAMPLE_RATE_DECREASE:
        frequency = frac1mul(inv_rate_scale, frequency) << 1
        bandwidth = frac1mul(inv_rate_scale, bandwidth) << 1
    elif sample_rate_change == SAMPLE_RATE_INCREASE:
        frequency = frac1mul(inv_rate_scale, frequency)
        bandwidth = frac1mul(inv_rate_scale, bandwidth)
    return frequency, bandwidth


def d2pole_cf45(
    inv_rate_scale: int,
    sample_rate_change: int,
    frequency: int,
    bandwidth: int,
    gain: int,
) -> tuple[int, int, int]:
    """Compute ``(acoef, bcoef, ccoef)`` for a cascade F4 / F5 resonator.

    Faithful translation of ``d2pole_cf45`` (``vtmfunc.h`` lines
    106-190). Over the Fs/2 cap: ``bcoef = ccoef = 0`` (DC pass-through
    with ``acoef = gain << 1``).

    Args:
        inv_rate_scale: Q15 inverse-rate scale.
        sample_rate_change: One of the SAMPLE_RATE_* constants.
        frequency: Resonator centre frequency in Hz.
        bandwidth: Resonator bandwidth in Hz.
        gain: Q12 gain term.

    Returns:
        ``(acoef, bcoef, ccoef)``.
    """
    frequency, bandwidth = _scale_freq_bw(
        frequency, bandwidth, inv_rate_scale, sample_rate_change
    )
    if frequency >= _FREQ_CAP or bandwidth > _BW_CAP:
        bcoef = 0
        ccoef = 0
    else:
        radius = radius_table[bandwidth >> 3]
        bcoef = frac4mul(radius, cosine_table[frequency >> 3])
        ccoef = -frac4mul(radius, radius)
    temp = 4096 - bcoef - ccoef
    acoef = frac4mul(gain, temp) << 1
    return acoef, bcoef, ccoef


def d2pole_cf123(
    sample_rate: int,
    inv_rate_scale: int,
    sample_rate_change: int,
    frequency: int,
    bandwidth: int,
    gain: int,
) -> tuple[int, int, int]:
    """Compute ``(acoef, bcoef, ccoef)`` for cascade F1 / F2 / F3.

    Faithful translation of ``d2pole_cf123`` (``vtmfunc.h`` lines
    208-290). Over the Fs/2 cap, freq/bw are clamped to ``Fs/2`` /
    ``Fs/4`` instead of zapping.

    Args:
        sample_rate: Output sample rate (``pKsd_t->uiSampleRate``).
        inv_rate_scale: Q15 inverse-rate scale.
        sample_rate_change: One of the SAMPLE_RATE_* constants.
        frequency: Resonator centre frequency in Hz.
        bandwidth: Resonator bandwidth in Hz.
        gain: Q12 gain term.

    Returns:
        ``(acoef, bcoef, ccoef)``.
    """
    frequency, bandwidth = _scale_freq_bw(
        frequency, bandwidth, inv_rate_scale, sample_rate_change
    )
    if frequency >= _FREQ_CAP or bandwidth > _BW_CAP:
        frequency = sample_rate >> 1
        bandwidth = sample_rate >> 2
    radius = radius_table[bandwidth >> 3]
    bcoef = frac4mul(radius, cosine_table[frequency >> 3])
    ccoef = -frac4mul(radius, radius)
    temp = 4096 - bcoef - ccoef
    acoef = frac4mul(gain, temp) << 1
    return acoef, bcoef, ccoef


def d2pole_pf(
    inv_rate_scale: int,
    sample_rate_change: int,
    frequency: int,
    bandwidth: int,
    gain: int,
) -> tuple[int, int, int]:
    """Compute ``(acoef, bcoef, ccoef)`` for a parallel-tract resonator.

    Faithful translation of ``d2pole_pf`` (``vtmfunc.h`` lines
    306-391). Over the Fs/2 cap, *all three coefficients* are
    zeroed — the resonator is silent.

    Args:
        inv_rate_scale: Q15 inverse-rate scale.
        sample_rate_change: One of the SAMPLE_RATE_* constants.
        frequency: Resonator centre frequency in Hz.
        bandwidth: Resonator bandwidth in Hz.
        gain: Q12 gain term.

    Returns:
        ``(acoef, bcoef, ccoef)`` — ``(0, 0, 0)`` when zapped.
    """
    frequency, bandwidth = _scale_freq_bw(
        frequency, bandwidth, inv_rate_scale, sample_rate_change
    )
    if frequency >= _FREQ_CAP or bandwidth > _BW_CAP:
        return 0, 0, 0
    radius = radius_table[bandwidth >> 3]
    bcoef = frac4mul(radius, cosine_table[frequency >> 3])
    ccoef = -frac4mul(radius, radius)
    temp = 4096 - bcoef - ccoef
    acoef = frac4mul(gain, temp) << 1
    return acoef, bcoef, ccoef
