"""Verify ``iso_to_upper`` and ``iso_to_lower`` match iso_char.c.

Re-builds the case-folding tables by running the same algorithm as
the C source's ``iso_case_map()`` (identity init + walk of
``case_table[]``) and asserts byte-for-byte equality.

Spot-checks ASCII case folding and one Latin-1 letter (À ↔ à); also
documents the preserved-bug entries for Ñ and Þ.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel import iso_char as ic

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/iso_char.c"
)
_H_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/include/iso_char.h"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file() or not _H_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_c_defines() -> dict[str, int]:
    """Parse every ``#define C_NAME 0xNN`` from iso_char.h."""
    text = _H_FILE.read_text(encoding="latin-1")
    out: dict[str, int] = {}
    for m in re.finditer(r"#define\s+(C_\w+)\s+(0x[0-9a-fA-F]+)", text):
        out[m.group(1)] = int(m.group(2), 16)
    return out


def _parse_case_table() -> tuple[tuple[int, int], ...]:
    """Parse ``case_table[] = { {C_A, C_a}, ... };`` from iso_char.c."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"struct\s+case_equivalents\s+case_table\[\]\s*=\s*\{(.+?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    names = _parse_c_defines()
    out: list[tuple[int, int]] = []
    for rec in re.finditer(r"\{\s*(\w+)\s*,\s*(\w+)\s*\}", body):
        upper_name = rec.group(1)
        lower_name = rec.group(2)
        if upper_name == "0" and lower_name == "0":
            continue  # terminator
        out.append((names[upper_name], names[lower_name]))
    return tuple(out)


def _build_from_c_table() -> tuple[bytes, bytes]:
    """Replay the C ``iso_case_map()`` algorithm against the C source's table."""
    pairs = _parse_case_table()
    upper = bytearray(range(256))
    lower = bytearray(range(256))
    for upper_byte, lower_byte in pairs:
        lower[upper_byte] = lower_byte
        upper[lower_byte] = upper_byte
    return bytes(upper), bytes(lower)


def test_iso_to_lower_matches_c_source() -> None:
    """Byte-for-byte equality with the C ``iso_case_map()`` output."""
    expected_upper, expected_lower = _build_from_c_table()
    assert ic.iso_to_lower == expected_lower
    del expected_upper


def test_iso_to_upper_matches_c_source() -> None:
    """Byte-for-byte equality with the C ``iso_case_map()`` output."""
    expected_upper, expected_lower = _build_from_c_table()
    assert ic.iso_to_upper == expected_upper
    del expected_lower


def test_both_tables_have_256_entries() -> None:
    """Tables cover every byte value 0..255."""
    expected = 256
    assert len(ic.iso_to_upper) == expected
    assert len(ic.iso_to_lower) == expected


@pytest.mark.parametrize("c", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
def test_ascii_uppercase_folds_to_lowercase(c: str) -> None:
    """ASCII A..Z fold to a..z via ``iso_to_lower``."""
    assert ic.iso_to_lower[ord(c)] == ord(c.lower())


@pytest.mark.parametrize("c", "abcdefghijklmnopqrstuvwxyz")
def test_ascii_lowercase_folds_to_uppercase(c: str) -> None:
    """ASCII a..z fold to A..Z via ``iso_to_upper``."""
    assert ic.iso_to_upper[ord(c)] == ord(c.upper())


def test_digit_is_identity() -> None:
    """Digits are unchanged by either fold."""
    for c in "0123456789":
        assert ic.iso_to_upper[ord(c)] == ord(c)
        assert ic.iso_to_lower[ord(c)] == ord(c)


def test_latin1_a_grave_folds() -> None:
    """À (0xC0) ↔ à (0xE0)."""
    a_grave_upper = 0xC0
    a_grave_lower = 0xE0
    assert ic.iso_to_lower[a_grave_upper] == a_grave_lower
    assert ic.iso_to_upper[a_grave_lower] == a_grave_upper


def test_latin1_n_tilde_preserved_bug() -> None:
    """The C source has ``{C_TL_N, C_TL_N}`` — Ñ folds to itself (not ñ).

    This is a documented preserved bug for byte-parity with the binary.
    """
    n_tilde_upper = 0xD1
    n_tilde_lower = 0xF1
    # Lower-fold of Ñ should give ñ in correct code, but the C source's
    # typo leaves it as Ñ. Mirror that.
    assert ic.iso_to_lower[n_tilde_upper] == n_tilde_upper
    # ñ stays as ñ on both folds (never registered).
    assert ic.iso_to_upper[n_tilde_lower] == n_tilde_lower


def test_latin1_thorn_preserved_bug() -> None:
    """Þ (0xDE) folds to itself per the C source's `{C_THORN, C_THORN}`."""
    thorn_upper = 0xDE
    assert ic.iso_to_lower[thorn_upper] == thorn_upper
