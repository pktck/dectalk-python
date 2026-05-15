"""Bit-parity tests for :func:`dectalk.dic.print_helpers.print_fc` / ``print_tf``.

Validates byte-for-byte equivalence with ``dic_comm.c``'s C originals:
the bit-walker drops in every form-class string for each set bit, the
zero case yields ``" none"``, and the T/F helper just picks ``,T`` or
``,F``.
"""

from __future__ import annotations

import pytest

from dectalk.dic.print_helpers import form_class_strings, print_fc, print_tf


def test_print_fc_zero_returns_none() -> None:
    """The C source emits ``" none"`` for a zero bitmask."""
    assert print_fc(0) == " none"


def test_print_fc_single_bit() -> None:
    """Setting bit 0 yields the first form-class string (`` adj``)."""
    assert print_fc(1) == form_class_strings[0]
    assert print_fc(2) == form_class_strings[1]
    assert print_fc(4) == form_class_strings[2]


def test_print_fc_all_bits() -> None:
    """All 32 bits set emits every form-class string concatenated."""
    expected = "".join(form_class_strings)
    assert print_fc(0xFFFFFFFF) == expected


def test_print_fc_mixed_bits() -> None:
    """Walking bits 0, 2, 4 picks ``adj``, ``art``, ``be``."""
    assert print_fc(0b10101) == " adj art be"


def test_print_fc_bits_above_31_ignored() -> None:
    """The C loop only walks 32 bits; higher bits are silently dropped."""
    # 33rd bit alone -> no match in form_class_strings -> empty output
    # but the C source emits " none" only on zero, so high-only bits
    # produce an empty string.
    assert print_fc(1 << 32) == ""


@pytest.mark.parametrize(
    ("val", "expected"),
    [
        (0, ",F"),
        (1, ",T"),
        (-1, ",T"),
        (100, ",T"),
    ],
)
def test_print_tf(val: int, expected: str) -> None:
    """Non-zero -> ``,T``, zero -> ``,F``."""
    assert print_tf(val) == expected


def test_form_class_strings_has_32_entries() -> None:
    """Mirrors the C source's fixed-size 32-entry array."""
    assert len(form_class_strings) == 32
