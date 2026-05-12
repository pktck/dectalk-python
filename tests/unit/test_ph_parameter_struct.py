"""Verify the Parameter dataclass models viphdefs.h's PARAMETER."""

from __future__ import annotations

from dectalk.ph.parameter_struct import Parameter


def test_default_construction() -> None:
    """All fields default to zero / None."""
    p = Parameter()
    assert p.tarcur == 0
    assert p.durlin == 0
    assert p.deldip == 0
    assert p.dipcum == 0
    assert p.ftran == 0
    assert p.dftran == 0
    assert p.btran == 0
    assert p.dbtran == 0
    assert p.tbacktr == 0
    assert p.tspesh == 0
    assert p.pspesh == 0
    assert p.tarnex == 0
    assert p.tarlas == 0
    assert p.tarend == 0
    assert p.ndip is None
    assert p.outp is None


def test_field_count_matches_c_struct() -> None:
    """The 16 fields match the C ``PARAMETER`` struct."""
    fields = Parameter.__dataclass_fields__
    expected = {
        "tarcur",
        "durlin",
        "deldip",
        "dipcum",
        "ftran",
        "dftran",
        "btran",
        "dbtran",
        "tbacktr",
        "tspesh",
        "pspesh",
        "tarnex",
        "tarlas",
        "tarend",
        "ndip",
        "outp",
    }
    assert set(fields.keys()) == expected
    assert len(fields) == 16


def test_assignment_via_kwargs() -> None:
    """Fields can be set at construction time."""
    p = Parameter(tarcur=600, durlin=10, ftran=5, ndip=7, outp=12)
    assert p.tarcur == 600
    assert p.durlin == 10
    assert p.ftran == 5
    assert p.ndip == 7
    assert p.outp == 12


def test_uses_slots() -> None:
    """The dataclass uses ``slots=True`` — no ``__dict__`` is created."""
    p = Parameter()
    assert not hasattr(p, "__dict__")
