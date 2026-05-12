"""Verify the SpdChip dataclass models viphdefs.h's SPD_CHIP."""

from __future__ import annotations

from dectalk.ph.spdef_chip import SpdChip


def test_default_construction() -> None:
    """All fields default to zero."""
    chip = SpdChip()
    assert chip.r4cb == 0
    assert chip.r4cc == 0
    assert chip.speaker == 0
    assert chip.sex == 0


def test_field_count_matches_c_struct() -> None:
    """24 fields match the C ``SPD_CHIP`` struct."""
    fields = SpdChip.__dataclass_fields__
    expected = {
        "r4cb",
        "r4cc",
        "r5cb",
        "r5cc",
        "r4pb",
        "r5pb",
        "t0jit",
        "r5ca",
        "r4ca",
        "r3ca",
        "r2ca",
        "r1ca",
        "nopen1",
        "nopen2",
        "aturb",
        "fnscale",
        "afgain",
        "rnpgain",
        "azgain",
        "apgain",
        "notused",
        "osgain",
        "speaker",
        "sex",
    }
    assert set(fields.keys()) == expected
    assert len(fields) == 24


def test_kwargs_construction() -> None:
    """Fields are settable via construction kwargs."""
    chip = SpdChip(
        r4cb=100,
        r4cc=3000,
        r5cb=200,
        r5cc=4000,
        speaker=2,  # Harry
        sex=1,
    )
    assert chip.r4cb == 100
    assert chip.r5cc == 4000
    assert chip.speaker == 2
    assert chip.sex == 1


def test_uses_slots() -> None:
    """SpdChip uses slots=True."""
    chip = SpdChip()
    assert not hasattr(chip, "__dict__")
