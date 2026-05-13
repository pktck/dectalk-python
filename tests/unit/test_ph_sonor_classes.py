"""Verify sonorant class / boundary constants from ph_setar.c."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import sonor_classes as sc

_C_SOURCE: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_setar.c")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``."""
    if not _C_SOURCE.exists():
        return None
    text = _C_SOURCE.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(-?\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1))
    return None


@pytest.mark.skipif(not _C_SOURCE.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FRONT_VOWEL", "FRONT_VOWEL", 1),
        ("BACK_UNROUNDED_VOWEL", "BACK_UNROUNDED_VOWEL", 2),
        ("BACK_ROUNDED_VOWEL", "BACK_ROUNDED_VOWEL", 3),
        ("OBSTRUENT", "OBSTRUENT", 4),
        ("ROUNDED_SONOR_CONS", "ROUNDED_SONOR_CONS", 5),
        ("ASPIRATION_AMPLITUDE", "ASPIRATION_AMPLITUDE", 42),
    ],
)
def test_sonor_class_matches_c(py_attr: str, c_name: str, expected: int) -> None:
    """Each sonorant-class constant matches ph_setar.c."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(sc, py_attr) == expected


def test_classes_form_dense_set() -> None:
    """The 5 classes form a dense 1..5 set."""
    classes = {
        sc.FRONT_VOWEL,
        sc.BACK_UNROUNDED_VOWEL,
        sc.BACK_ROUNDED_VOWEL,
        sc.OBSTRUENT,
        sc.ROUNDED_SONOR_CONS,
    }
    assert classes == {1, 2, 3, 4, 5}


def test_initial_final_complementary() -> None:
    """``INITIAL`` (False) and ``FINAL`` (True) are complementary booleans."""
    assert sc.INITIAL is False
    assert sc.FINAL is True
    assert sc.INITIAL != sc.FINAL
