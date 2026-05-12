"""Verify PhonemeMark / PhonemeMark2 dataclasses."""

from __future__ import annotations

from dectalk.api.phoneme_mark import PhonemeMark, PhonemeMark2


def test_phoneme_mark_defaults() -> None:
    """PhonemeMark defaults to (0, 0, 0)."""
    pm = PhonemeMark()
    assert pm.c_this_phoneme == 0
    assert pm.c_next_phoneme == 0
    assert pm.w_duration == 0


def test_phoneme_mark2_defaults() -> None:
    """PhonemeMark2 defaults to (0, 0, 0)."""
    pm = PhonemeMark2()
    assert pm.c_this_phoneme == 0
    assert pm.c_next_phoneme == 0
    assert pm.w_duration == 0


def test_phoneme_mark_construction() -> None:
    """Fields are settable at construction."""
    pm = PhonemeMark(c_this_phoneme=42, c_next_phoneme=43, w_duration=80)
    assert pm.c_this_phoneme == 42
    assert pm.c_next_phoneme == 43
    assert pm.w_duration == 80


def test_phoneme_mark2_can_hold_16bit() -> None:
    """PhonemeMark2 accepts 16-bit values that wouldn't fit in PhonemeMark."""
    pm = PhonemeMark2(c_this_phoneme=0x1E2D, c_next_phoneme=0x1E2C, w_duration=120)
    assert pm.c_this_phoneme == 0x1E2D
    assert pm.c_next_phoneme == 0x1E2C
    assert pm.w_duration == 120


def test_both_use_slots() -> None:
    """Both dataclasses use slots=True (no __dict__)."""
    assert not hasattr(PhonemeMark(), "__dict__")
    assert not hasattr(PhonemeMark2(), "__dict__")


def test_field_counts() -> None:
    """Both structs have 3 fields each."""
    assert len(PhonemeMark.__dataclass_fields__) == 3
    assert len(PhonemeMark2.__dataclass_fields__) == 3
