"""Verify the cm_copt.c preamble tables match the C source.

Re-parses the five ``const phoneme_t preamble_*[]`` arrays at test
time (resolving PSNEXTRA/PSFONT/PFUSA/US_*/S2/WBOUND/COMMA to
numeric constants) and asserts every record matches our Python
literal exactly.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import preamble_tables as pt
from dectalk.include.phoneme_codes import (
    COMMA,
    S1,
    S2,
    SBOUND,
    WBOUND,
    USPhoneme,
)

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/cmd/cm_copt.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)

_PSNEXTRA = 13
_PSFONT = 8
_PFUSA = 0x1E

_SYMBOLS: dict[str, int] = {
    "PSNEXTRA": _PSNEXTRA,
    "PSFONT": _PSFONT,
    "PFUSA": _PFUSA,
    "S1": S1,
    "S2": S2,
    "WBOUND": WBOUND,
    "COMMA": COMMA,
    "SBOUND": SBOUND,
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
}


def _eval_field(expr: str) -> int:
    """Resolve symbolic constants in a C field expression.

    Handles patterns like ``(2<<PSNEXTRA) | (PFUSA<<PSFONT) | US_M``.
    """
    expr = expr.strip()
    for name in sorted(_SYMBOLS.keys(), key=len, reverse=True):
        expr = re.sub(r"\b" + re.escape(name) + r"\b", str(_SYMBOLS[name]), expr)
    return eval(expr)


def _parse_preamble(name: str) -> tuple[pt.Phoneme, ...]:
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+phoneme_t\s+{re.escape(name)}\[\]\s*=\s*\{{(.+?)\}};",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name}"
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    records: list[pt.Phoneme] = []
    for rec in re.finditer(r"\{([^{}]+)\}", body):
        fields = [f.strip() for f in rec.group(1).split(",")]
        assert len(fields) == 4
        phone, dur, pitch, nextra = (_eval_field(f) for f in fields)
        records.append(pt.Phoneme(phone=phone, dur=dur, pitch=pitch, nextra=nextra))
    return tuple(records)


@pytest.mark.parametrize(
    ("name", "py_table"),
    [
        ("preamble_1", pt.preamble_1),
        ("preamble_2a", pt.preamble_2a),
        ("preamble_2b", pt.preamble_2b),
        ("preamble_3a", pt.preamble_3a),
        ("preamble_3b", pt.preamble_3b),
    ],
)
def test_preamble_matches_c_source(name: str, py_table: tuple[pt.Phoneme, ...]) -> None:
    """Each preamble matches the C source initialiser record-for-record."""
    expected = _parse_preamble(name)
    assert py_table == expected


def test_preamble_1_decodes_to_message_comma() -> None:
    """Preamble 1's last record is COMMA + WBOUND (the trailing ", " marker)."""
    # Each entry's low 8 bits are the phoneme/control code.
    low_byte_mask = 0xFF
    codes = [p.phone & low_byte_mask for p in pt.preamble_1]
    # End: COMMA, WBOUND
    assert codes[-2] == COMMA
    assert codes[-1] == WBOUND


def test_preamble_2a_starts_with_us_m() -> None:
    """First record's low 8 bits = US_M (the M of "Message")."""
    low_byte_mask = 0xFF
    assert pt.preamble_2a[0].phone & low_byte_mask == int(USPhoneme.M)


def test_preamble_records_have_pfusa_font() -> None:
    """Every record's middle bits encode PFUSA (US English font)."""
    font_mask = 0x1F00  # bits 8-12
    font_shift = 8
    for table_name in ("preamble_1", "preamble_2a", "preamble_2b", "preamble_3a", "preamble_3b"):
        table = getattr(pt, table_name)
        for i, record in enumerate(table):
            font = (record.phone & font_mask) >> font_shift
            assert font == _PFUSA, f"{table_name}[{i}] font={font:#x}"


def test_phoneme_dataclass_is_frozen() -> None:
    """The Phoneme record type is immutable (tuples are hashable)."""
    p = pt.Phoneme(0, 0, 0, 0)
    with pytest.raises((AttributeError, Exception)):
        p.phone = 1  # type: ignore[misc]
