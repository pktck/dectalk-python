"""Verify BIN_* binary-rule opcodes match par_bin.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import par_bin_codes as bc

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/par_bin.h")


def _parse_defines() -> dict[str, int] | None:
    """Return ``#define BIN_<NAME> <hex>`` pairs from par_bin.h."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    out: dict[str, int] = {}
    for m in re.finditer(
        r"^#define\s+(BIN_[A-Z_]+)\s+(0x[0-9A-Fa-f]+|\d+)\s*(?:/\*.*?\*/)?\s*$",
        text,
        re.MULTILINE,
    ):
        name = m.group(1)
        if name in out:
            continue
        tok = m.group(2)
        out[name] = int(tok, 16) if tok.lower().startswith("0x") else int(tok)
    return out


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_every_define_matches_c() -> None:
    """Every C ``#define BIN_*`` matches the Python constant."""
    c_defs = _parse_defines()
    assert c_defs is not None
    for name, value in c_defs.items():
        py_value = getattr(bc, name, None)
        assert py_value is not None, f"missing Python constant {name}"
        assert py_value == value, f"{name}: C={value:#x}, Py={py_value:#x}"


def test_op_mask_and_flag_mask_partition_byte() -> None:
    """``BIN_OPERATION_MASK`` (0x1F) + ``BIN_OPERATION_FLAG_MASK`` (0xE0) = 0xFF."""
    assert bc.BIN_OPERATION_MASK | bc.BIN_OPERATION_FLAG_MASK == 0xFF
    assert bc.BIN_OPERATION_MASK & bc.BIN_OPERATION_FLAG_MASK == 0


def test_after_alias_comp_break() -> None:
    """``BIN_AFTER`` and ``BIN_COMP_BREAK`` are the same byte (0x1B)."""
    assert bc.BIN_AFTER == bc.BIN_COMP_BREAK == 0x1B


def test_digit_range_alias_case_insen() -> None:
    """``BIN_DIGIT_RANGE`` and ``BIN_CASE_INSEN`` share bit 0x20."""
    assert bc.BIN_DIGIT_RANGE == bc.BIN_CASE_INSEN == 0x20


def test_end_of_rule_is_zero() -> None:
    """``BIN_END_OF_RULE`` is 0 — terminates a rule sequence."""
    assert bc.BIN_END_OF_RULE == 0


def test_special_rule_top_three_bits() -> None:
    """``BIN_SPECIAL_RULE_MASK`` (0xE000) is the top 3 bits of 16."""
    assert bc.BIN_SPECIAL_RULE_MASK == 0xE000


def test_max_small_and_large_desc() -> None:
    """``BIN_MAX_SMALL_DESC`` (0x3F) fits in 6 bits; ``BIN_MAX_LARGE_DESC`` (0x3FFF) in 14."""
    assert bc.BIN_MAX_SMALL_DESC == 0x3F == (1 << 6) - 1
    assert bc.BIN_MAX_LARGE_DESC == 0x3FFF == (1 << 14) - 1
