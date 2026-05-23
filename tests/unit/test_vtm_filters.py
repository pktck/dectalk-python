"""Unit tests for the Q12 biquad filter primitives in vtm/filters.py."""

from __future__ import annotations

from dectalk.vtm.filters import (
    two_pole_filter,
    two_zero_filter,
    two_zero_filter_2,
)


class TestTwoPoleFilter:
    def test_zero_returns_zero(self) -> None:
        assert two_pole_filter(0, 0, 0, 0, 0, 0) == (0, 0)

    def test_unity_a_passthrough(self) -> None:
        # input=1000, a=4096 (unity Q12), b=c=0 -> output=1000.
        new_d1, new_d2 = two_pole_filter(1000, 0, 0, 4096, 0, 0)
        assert new_d1 == 1000
        assert new_d2 == 0

    def test_delay_2_catches_old_delay_1(self) -> None:
        _, new_d2 = two_pole_filter(0, 7777, 1234, 0, 0, 0)
        assert new_d2 == 7777

    def test_b_coef_feedback(self) -> None:
        # delay_1=4096, b=4096 -> (4096*4096)>>12 = 4096
        new_d1, _ = two_pole_filter(0, 4096, 0, 0, 4096, 0)
        assert new_d1 == 4096

    def test_c_coef_feedback(self) -> None:
        new_d1, _ = two_pole_filter(0, 0, 4096, 0, 0, 4096)
        assert new_d1 == 4096

    def test_negative_input_arithmetic_shift(self) -> None:
        new_d1, _ = two_pole_filter(-3, 0, 0, 4096, 0, 0)
        assert new_d1 == -3


class TestTwoZeroFilter:
    def test_unity_a_passthrough(self) -> None:
        out, new_d1, new_d2 = two_zero_filter(2000, 0, 0, 4096, 0, 0)
        assert out == 2000
        assert new_d1 == 2000  # current input
        assert new_d2 == 0

    def test_delay_2_catches_old_delay_1(self) -> None:
        _, new_d1, new_d2 = two_zero_filter(50, 999, 100, 0, 0, 0)
        assert new_d1 == 50  # current input
        assert new_d2 == 999  # old delay_1

    def test_full_three_tap(self) -> None:
        out, new_d1, new_d2 = two_zero_filter(10, 20, 30, 4096, 4096, 4096)
        # (4096*10 + 4096*20 + 4096*30) >> 12 = 60
        assert out == 60
        assert new_d1 == 10
        assert new_d2 == 20


class TestTwoZeroFilter2:
    def test_zero_state_returns_input(self) -> None:
        new_input, new_d1, new_d2 = two_zero_filter_2(5000, 0, 0, 0, 0)
        assert new_input == 5000
        assert new_d1 == 5000
        assert new_d2 == 0

    def test_b_c_modulation(self) -> None:
        # delay_1=100, delay_2=200, b=c=4096 (unity) -> input += 300
        new_input, new_d1, new_d2 = two_zero_filter_2(1000, 100, 200, 4096, 4096)
        assert new_input == 1300
        assert new_d1 == 1000
        assert new_d2 == 100

    def test_negative_b(self) -> None:
        new_input, _, _ = two_zero_filter_2(500, 200, 0, -2048, 0)
        # input += (-2048*200) >> 12 = -100
        assert new_input == 400
