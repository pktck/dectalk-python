"""Verify SPC packet-type / subtype / flush / mode codes from kernel.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.kernel import spc_codes as spc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/kernel.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int-or-hex>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    # The kernel.h source wraps some values in parens — strip them.
    pattern = rf"^#define\s+{re.escape(name)}\s+\(?(0[xX][0-9A-Fa-f]+|\d+)\)?\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("SPC_TYPE_MASK", "SPC_TYPE_MASK", 0x00FF),
        ("SPC_type_voice", "SPC_type_voice", 0),
        ("SPC_type_speaker", "SPC_type_speaker", 1),
        ("SPC_type_tone", "SPC_type_tone", 2),
        ("SPC_type_test", "SPC_type_test", 3),
        ("SPC_type_nop", "SPC_type_nop", 4),
        ("SPC_type_digitized", "SPC_type_digitized", 5),
        ("SPC_type_mixed", "SPC_type_mixed", 6),
        ("SPC_type_index", "SPC_type_index", 7),
        ("SPC_type_sync", "SPC_type_sync", 8),
        ("SPC_type_flush", "SPC_type_flush", 9),
        ("SPC_type_flush_sync", "SPC_type_flush_sync", 10),
        ("SPC_type_force", "SPC_type_force", 11),
        ("SPC_type_samples_per_frame", "SPC_type_samples_per_frame", 12),
        ("SPC_type_visual", "SPC_type_visual", 128),
        ("SPC_subtype_bookmark", "SPC_subtype_bookmark", 0x0100),
        ("SPC_subtype_wordpos", "SPC_subtype_wordpos", 0x0200),
        ("SPC_subtype_start", "SPC_subtype_start", 0x0300),
        ("SPC_subtype_stop", "SPC_subtype_stop", 0x0400),
        ("SPC_subtype_sentence", "SPC_subtype_sentence", 0x0500),
        ("SPC_subtype_volume", "SPC_subtype_volume", 0x0600),
        ("SPC_subtype_noise", "SPC_subtype_noise", 0x0700),
        ("SPC_flush_all", "SPC_flush_all", 0),
        ("SPC_flush_until", "SPC_flush_until", 1),
        ("SPC_flush_mask", "SPC_flush_mask", 2),
        ("SPC_flush_after", "SPC_flush_after", 3),
        ("SPC_mode_text", "SPC_mode_text", 0),
        ("SPC_mode_digital", "SPC_mode_digital", 1),
        ("MAX_SPC_DATA", "MAX_SPC_DATA", 32),
        ("MAX_SPC_PACKETS", "MAX_SPC_PACKETS", 400),
        ("PHONE_HUGE", "PHONE_HUGE", 9999),
    ],
)
def test_spc_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each SPC constant matches kernel.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None, f"{c_name} not parseable"
    assert c_value == expected
    assert getattr(spc, py_attr) == expected


def test_type_mask_matches_type_field_width() -> None:
    """``SPC_TYPE_MASK`` extracts exactly the low byte of a packet header."""
    assert spc.SPC_TYPE_MASK == 0xFF
    # Each SPC_type_* fits in the masked byte.
    for v in (
        spc.SPC_type_voice,
        spc.SPC_type_speaker,
        spc.SPC_type_tone,
        spc.SPC_type_test,
        spc.SPC_type_visual,
    ):
        assert v == (v & spc.SPC_TYPE_MASK)


def test_subtypes_in_second_byte() -> None:
    """All SPC_subtype_* values sit in the second byte (0x?100..0x?700)."""
    for v in (
        spc.SPC_subtype_bookmark,
        spc.SPC_subtype_wordpos,
        spc.SPC_subtype_start,
        spc.SPC_subtype_stop,
        spc.SPC_subtype_sentence,
        spc.SPC_subtype_volume,
        spc.SPC_subtype_noise,
    ):
        assert (v & 0xFF) == 0
        assert 0x0100 <= v <= 0xFF00
