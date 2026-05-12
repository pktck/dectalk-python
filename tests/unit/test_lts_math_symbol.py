"""Verify the MathSymbol dataclass."""

from __future__ import annotations

from dectalk.lts.math_symbol import MathSymbol


def test_default() -> None:
    """Defaults are (0, b'')."""
    ms = MathSymbol()
    assert ms.sym == 0
    assert ms.sym_pron == b""


def test_plus() -> None:
    """A ``+`` → ``plus`` entry."""
    ms = MathSymbol(sym=ord("+"), sym_pron=b"pl'^s")
    assert ms.sym == ord("+")
    assert ms.sym_pron == b"pl'^s"


def test_minus() -> None:
    """A ``-`` → ``minus`` entry."""
    ms = MathSymbol(sym=ord("-"), sym_pron=b"m'An|s")
    assert ms.sym == ord("-")
    assert ms.sym_pron == b"m'An|s"


def test_uses_slots() -> None:
    """MathSymbol uses slots=True."""
    ms = MathSymbol()
    assert not hasattr(ms, "__dict__")


def test_field_count() -> None:
    """The 2 fields match the C struct."""
    fields = MathSymbol.__dataclass_fields__
    assert set(fields.keys()) == {"sym", "sym_pron"}
