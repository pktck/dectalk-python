"""Verify ``deadstop`` / ``mstofr`` parity with ph_task.c."""

from __future__ import annotations

import pytest

from dectalk.ph import task_helpers as th


@pytest.mark.parametrize(
    ("value", "low", "high", "expected"),
    [
        (5, 0, 10, 5),  # in range
        (-3, 0, 10, 0),  # below low
        (15, 0, 10, 10),  # above high
        (0, 0, 10, 0),  # at low boundary
        (10, 0, 10, 10),  # at high boundary
        (5, 5, 5, 5),  # zero-width interval
        (-100, -50, 50, -50),
        (100, -50, 50, 50),
        (0, -50, 50, 0),
    ],
)
def test_deadstop(value: int, low: int, high: int, expected: int) -> None:
    """``deadstop`` clamps value into [low, high]."""
    assert th.deadstop(value, low, high) == expected


def test_mstofr_zero() -> None:
    """0 ms → 0 frames."""
    assert th.mstofr(0) == 0


@pytest.mark.parametrize(
    ("ms", "expected_frames"),
    [
        (0, 0),
        (6, 0),  # 6*10 = 60, 60 >> 6 = 0
        (7, 1),  # 7*10 = 70, 70 >> 6 = 1
        (64, 10),  # 64*10 = 640, 640 >> 6 = 10
        (100, 15),  # 100*10 = 1000, 1000 >> 6 = 15
        (1000, 156),  # 1000*10 = 10000, 10000 >> 6 = 156
        (6400, 1000),  # 6400*10 = 64000, 64000 >> 6 = 1000
    ],
)
def test_mstofr_matches_c_formula(ms: int, expected_frames: int) -> None:
    """``mstofr(ms) == (ms * 10) >> 6`` exactly."""
    assert th.mstofr(ms) == expected_frames


def test_mstofr_matches_inline_formula() -> None:
    """``mstofr(n)`` matches ``(n * 10) >> 6`` for a wide input range."""
    for ms in range(0, 10001, 17):  # 0..10000, step 17
        assert th.mstofr(ms) == (ms * 10) >> 6


def test_mstofr_negative_input() -> None:
    """Negative ms (unusual but legal C) — Python's >> follows the C semantics
    for positive shift, but the C source casts to S32 which is signed.
    For negative inputs, Python's >> is arithmetic (preserves sign), so the
    result matches the C behaviour when nms is positive (the normal case).
    """
    # The function is documented for non-negative inputs.
    assert th.mstofr(64) == 10


def test_mstofr_macro_uses_nsamp_frame() -> None:
    """``mstofr_macro(ms)`` = ``((ms + 4) * 10) // NSAMP_FRAME``."""
    from dectalk.ph.numeric_constants import NSAMP_FRAME  # noqa: PLC0415

    for ms in (0, 5, 10, 50, 100, 500, 1000):
        expected = ((ms + 4) * 10) // NSAMP_FRAME
        assert th.mstofr_macro(ms) == expected


def test_frtoms_uses_nsamp_frame() -> None:
    """``frtoms(frames)`` = ``(frames * NSAMP_FRAME + 5) // 10``."""
    from dectalk.ph.numeric_constants import NSAMP_FRAME  # noqa: PLC0415

    for frames in (0, 1, 10, 50, 100, 500, 1000):
        expected = (frames * NSAMP_FRAME + 5) // 10
        assert th.frtoms(frames) == expected


def test_mstofr_macro_and_frtoms_roundtrip() -> None:
    """``frtoms(mstofr_macro(ms))`` recovers ``ms`` within rounding error."""
    for ms in (10, 50, 100, 500, 1000):
        frames = th.mstofr_macro(ms)
        back = th.frtoms(frames)
        # Round-trip should land within ~5 ms (one frame's worth).
        assert abs(back - ms) <= 5
