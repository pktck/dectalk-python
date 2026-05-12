"""Verify the AsckyTab dataclass."""

from __future__ import annotations

from dectalk.cmd.ascky_struct import AsckyTab


def test_default() -> None:
    """Defaults are (0, 0)."""
    ascky = AsckyTab()
    assert ascky.p_graph == 0
    assert ascky.p_phone_phone == 0


def test_construction() -> None:
    """Fields are settable."""
    ascky = AsckyTab(p_graph=ord("e"), p_phone_phone=0x1E03)
    assert ascky.p_graph == ord("e")
    assert ascky.p_phone_phone == 0x1E03


def test_uses_slots() -> None:
    """AsckyTab uses slots=True."""
    ascky = AsckyTab()
    assert not hasattr(ascky, "__dict__")


def test_field_count() -> None:
    """The 2 fields match the C ``ASCKY_TAB`` struct."""
    fields = AsckyTab.__dataclass_fields__
    assert set(fields.keys()) == {"p_graph", "p_phone_phone"}
