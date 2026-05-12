"""Verify ``tone`` / ``tone_exact`` parity with playtone.c."""

from __future__ import annotations

import math

import pytest

from dectalk.vtm import tone as t
from dectalk.vtm.sinetab import TWO_PI_EQUIVALENT, SineTable


def test_tone_returns_sine_table_lookup() -> None:
    """The sample equals ``SineTable[int(phase)]``."""
    sample, _ = t.tone(1.0, 100.5)
    assert sample == SineTable[100]


def test_tone_advances_phase() -> None:
    """The new phase = ``phase + increment``."""
    _, new_phase = t.tone(5.5, 100.0)
    assert new_phase == 105.5


def test_tone_wraps_at_two_pi_equivalent() -> None:
    """Phase wraps back when it crosses TWO_PI_EQUIVALENT."""
    # phase 1020 + increment 10 = 1030 ≥ 1024 → wraps to 6
    _, new_phase = t.tone(10.0, 1020.0)
    assert new_phase == 1030.0 - TWO_PI_EQUIVALENT


def test_tone_zero_phase_zero_sample() -> None:
    """sin(0) ≈ 0, and SineTable[0] == 0 exactly."""
    sample, _ = t.tone(1.0, 0.0)
    assert sample == 0.0


def test_tone_quarter_phase_one_sample() -> None:
    """At 1/4 of the table (256/1024), the sine is ≈ 1."""
    sample, _ = t.tone(1.0, 256.0)
    assert abs(sample - 1.0) < 1e-3


@pytest.mark.parametrize("phase", [0.0, 256.0, 512.0, 768.0, 1023.0])
def test_tone_consecutive_calls_match_table(phase: float) -> None:
    """Repeated calls at any phase give the SineTable value at that index."""
    sample, new_phase = t.tone(0.0, phase)  # zero increment — phase stays
    assert sample == SineTable[int(phase)]
    assert new_phase == phase


# ---- tone_exact (non-LOWCOMPUTE branch) ----


def test_tone_exact_returns_sin() -> None:
    """``tone_exact`` returns ``math.sin(phase)``."""
    sample, _ = t.tone_exact(0.1, math.pi / 4)
    assert abs(sample - math.sin(math.pi / 4)) < 1e-9


def test_tone_exact_advances_phase() -> None:
    """The new phase = ``phase + increment``."""
    _, new_phase = t.tone_exact(0.5, 1.0)
    assert new_phase == 1.5


def test_tone_exact_wraps_at_two_pi() -> None:
    """tone_exact wraps at 2*pi (its TWO_PI_EQUIVALENT is radians)."""
    _, new_phase = t.tone_exact(2 * math.pi - 0.001, math.pi)
    # phase (pi) + increment (2pi - 0.001) = 3pi - 0.001 > 2pi → wraps
    assert abs(new_phase - (math.pi - 0.001)) < 1e-6
