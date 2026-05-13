"""Verify muldv / mlsh1 match ph_defs.h."""

from __future__ import annotations

from dectalk.ph.math_helpers import mlsh1, muldv


def test_muldv_basic() -> None:
    """``(x * y) / z`` works on small positives."""
    assert muldv(10, 20, 5) == 40
    assert muldv(100, 50, 25) == 200


def test_muldv_truncates_toward_zero() -> None:
    """C integer division truncates toward zero, not floor."""
    assert muldv(7, 1, 2) == 3  # 7 // 2 = 3 (positive: same as floor)
    assert muldv(-7, 1, 2) == -3  # C truncates -7/2 to -3, not -4
    assert muldv(7, -1, 2) == -3
    assert muldv(-7, -1, 2) == 3


def test_muldv_intermediate_widens_to_s32() -> None:
    """Intermediate ``x * y`` widens to 32-bit before division."""
    # 1000 * 1000 = 1_000_000 exceeds 16-bit signed max (32767).
    # C: ((S32)1000 * (S32)1000) / (S32)100 = 10_000
    assert muldv(1000, 1000, 100) == 10_000


def test_muldv_with_frac_one_pattern() -> None:
    """Used as ``muldv(FRAC_ONE, temp2, temp3)`` in init_timing."""
    frac_one = 16384
    # init_timing pattern: temp2 = 400 - sprat0, temp3 = 220
    assert muldv(frac_one, 200, 220) == 14894


def test_mlsh1_q14_unity() -> None:
    """Q14 unity (16384) * x returns x (within Q14 truncation)."""
    frac_one = 16384
    assert mlsh1(frac_one, 100) == 100
    assert mlsh1(frac_one, 0) == 0


def test_mlsh1_q14_half() -> None:
    """Q14 0.5 (8192) * 1000 returns 500."""
    half = 8192
    assert mlsh1(half, 1000) == 500


def test_mlsh1_truncates_to_s16() -> None:
    """Result is truncated back into 16-bit signed range."""
    # 30000 * 30000 = 9e8; >> 14 = 54931, truncates to 16-bit signed: -10605.
    result = mlsh1(30_000, 30_000)
    assert -32768 <= result <= 32767
    # Verify the wraparound (matches C short cast).
    expected = (30_000 * 30_000) >> 14
    expected_16 = expected if expected < 0x8000 else expected - 0x10000
    assert result == expected_16


def test_mlsh1_handles_negatives() -> None:
    """Negative inputs preserve sign through the 32-bit intermediate."""
    frac_one = 16384
    assert mlsh1(frac_one, -100) == -100
    assert mlsh1(-frac_one, 100) == -100
    assert mlsh1(-frac_one, -100) == 100
