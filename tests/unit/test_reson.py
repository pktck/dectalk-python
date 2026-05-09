"""Unit tests for the second-order resonator (`dectalk.hlsyn.reson`).

These tests verify three things:
1. Coefficient computation matches the C source's algebra exactly.
2. Per-sample :meth:`advance` matches a hand-computed difference equation.
3. The vectorized :meth:`process` produces the same output as
   `advance` called in a loop, validating the lfilter state translation.
"""

from __future__ import annotations

import math

import numpy as np

from dectalk.hlsyn.reson import MIN_RESON, Resonator


def _close(a: float, b: float, *, rel: float = 1e-7, abs_tol: float = 1e-9) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def test_default_resonator_state_is_zero() -> None:
    r = Resonator()
    assert (r.a, r.b, r.c, r.z1, r.z2) == (0.0, 0.0, 0.0, 0.0, 0.0)


def test_clear_resets_state_only() -> None:
    r = Resonator(a=0.5, b=0.4, c=-0.3, z1=1.0, z2=2.0)
    r.clear()
    assert r.z1 == 0.0
    assert r.z2 == 0.0
    assert (r.a, r.b, r.c) == (0.5, 0.4, -0.3)


def test_set_pole_pair_matches_c_algebra() -> None:
    """Verify SetPolePair coefficient formulas from the C source."""
    r = Resonator()
    cf, bw, sf = 500.0, 50.0, 11025.0
    r.set_pole_pair(cf, bw, sf)

    pi_t = math.pi / sf
    mag = math.exp(-pi_t * bw)
    angle = 2.0 * pi_t * cf
    expected_c = -mag * mag
    expected_b = mag * math.cos(angle) * 2.0
    expected_a = 1.0 - expected_b - expected_c

    assert _close(r.a, expected_a)
    assert _close(r.b, expected_b)
    assert _close(r.c, expected_c)


def test_advance_implements_difference_equation() -> None:
    """y[n] = A*x[n] + B*y[n-1] + C*y[n-2]."""
    r = Resonator(a=0.3, b=0.5, c=-0.2)
    y0 = r.advance(1.0)
    assert _close(y0, 0.3)
    y1 = r.advance(1.0)
    # y1 = 0.3*1 + 0.5*0.3 + (-0.2)*0 = 0.45
    assert _close(y1, 0.45)
    y2 = r.advance(1.0)
    # y2 = 0.3*1 + 0.5*0.45 + (-0.2)*0.3 = 0.465
    assert _close(y2, 0.465)


def test_advance_flushes_denormals() -> None:
    """Outputs whose magnitude falls below MIN_RESON are flushed to zero."""
    r = Resonator(a=MIN_RESON / 100.0)
    y = r.advance(1.0)
    assert y == 0.0
    assert r.z1 == 0.0


def test_anti_resonator_state_holds_input_not_output() -> None:
    """advance_anti updates state with input, distinguishing it from advance."""
    r = Resonator(a=1.0, b=0.0, c=0.0)
    r.advance_anti(7.0)
    assert r.z1 == 7.0  # input, not output


def test_set_zero_pair_inverts_pole_pair() -> None:
    """Multiplying a zero-pair filter by its corresponding pole pair gives unity gain at DC."""
    cf, bw, sf = 1500.0, 100.0, 11025.0
    pole = Resonator()
    pole.set_pole_pair(cf, bw, sf)
    zero = Resonator()
    zero.set_zero_pair(cf, bw, sf)

    # Run a unit impulse through pole then zero; expect a delta at sample 0.
    impulse = np.zeros(50, dtype=np.float64)
    impulse[0] = 1.0
    intermediate = np.fromiter((pole.advance(float(s)) for s in impulse), dtype=np.float64)
    out = np.fromiter((zero.advance_anti(float(s)) for s in intermediate), dtype=np.float64)
    # Cascade(pole, anti) ≈ identity for ideal pole-zero cancellation. Allow
    # numerical slop from the magnitude-squared exponential roundoff.
    assert _close(float(out[0]), 1.0, rel=1e-6, abs_tol=1e-6)
    assert np.max(np.abs(out[1:])) < 1e-3


def test_process_matches_per_sample_loop() -> None:
    """Vectorized buffer API must match the per-sample loop within float epsilon."""
    cf, bw, sf = 500.0, 60.0, 11025.0
    rng = np.random.default_rng(42)
    samples = rng.standard_normal(2000).astype(np.float64)

    r_loop = Resonator()
    r_loop.set_pole_pair(cf, bw, sf)
    out_loop = np.fromiter((r_loop.advance(float(s)) for s in samples), dtype=np.float64)

    r_vec = Resonator()
    r_vec.set_pole_pair(cf, bw, sf)
    out_vec = r_vec.process(samples)

    # The denormal flush in advance() is not applied in the vectorized path,
    # so allow a tiny absolute tolerance — but the bulk of the signal must
    # agree to within standard float64 roundoff.
    np.testing.assert_allclose(out_vec, out_loop, atol=MIN_RESON * 2, rtol=1e-9)


def test_process_state_persists_across_calls() -> None:
    """Splitting a buffer in two and processing each half must equal a single-shot call."""
    cf, bw, sf = 1200.0, 80.0, 11025.0
    rng = np.random.default_rng(0)
    samples = rng.standard_normal(1024).astype(np.float64)

    r_one = Resonator()
    r_one.set_pole_pair(cf, bw, sf)
    out_one = r_one.process(samples)

    r_two = Resonator()
    r_two.set_pole_pair(cf, bw, sf)
    out_two_a = r_two.process(samples[:512])
    out_two_b = r_two.process(samples[512:])
    out_two = np.concatenate([out_two_a, out_two_b])

    np.testing.assert_allclose(out_two, out_one, atol=1e-9)


def test_inter_pole_pair_smooths_state() -> None:
    """InterPolePair rescales state when the new A differs from the old one."""
    r = Resonator(a=0.4, b=0.3, c=-0.1, z1=1.0, z2=2.0)
    old_z1, old_z2 = r.z1, r.z2
    r.inter_pole_pair(700.0, 80.0, 11025.0)
    if r.a != 0.4:
        assert r.z1 != old_z1 or r.z2 != old_z2
